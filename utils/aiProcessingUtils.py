import traceback
import time
import asyncio
from fastapi import HTTPException
from utils.refineTextPrompt import prompt
from utils.episodePrompt import episodePrompt
from openai import AsyncOpenAI
import os
from utils.tokenCount import count_tokens
from utils.mailManager import mail_manager


processing_lock = asyncio.Lock()
processing_records = {}
key = os.getenv("OPENAI_API_KEY")

# Initialize your asynchronous OpenAI client.
client = AsyncOpenAI(api_key=key)


async def create_episode_with_llm(records, record_ids, user_id):
    """
    Background task to process text with LLM and update the database.
    This function runs independently of the HTTP request/response cycle.
    """
    from utils.supabaseUtils import supabase_func_instance

    final_process = mail_manager.compare_webhook_email(user_id)
    mail_manager.update_bg_task(user_id)

    try:
        # Filter records to only include those in record_ids
        filtered_records = [record for record in records if record["id"] in record_ids]
        unique_emails = list(
            set(record["email_address"] for record in filtered_records)
        )
        user_id = user_id

        await supabase_func_instance.supabase.table("user_news_letters").update(
            {"episode_flag": True}
        ).in_("id", record_ids).execute()

        if not filtered_records:
            print(f"No matching records found for IDs: {record_ids}")
            return

        # Create a dictionary of newsletter content
        newsletter_dict = {}
        for index, record in enumerate(filtered_records):
            # Use the full refined_text instead of just the first 10 characters
            newsletter_dict[index + 1] = record["refined_text"]

        # Format the content for the prompt
        news_letter_content_str = "\n\n".join(
            [f"Newsletter {key}:\n{value}" for key, value in newsletter_dict.items()]
        )

        # Format the prompt

        print(f"📩 Processing episode for {len(filtered_records)} newsletters")

        # Prepare the conversation history
        history = [
            {
                "role": "system",
                "content": episodePrompt,
            },
            {"role": "user", "content": news_letter_content_str},
        ]

        # Call the OpenAI model
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=history,
            temperature=0,
            response_format={"type": "json_object"},  # Force JSON response
        )

        episode_text = response.choices[0].message.content.strip()

        # print(episode_text)

        import json

        try:
            episode_data = json.loads(episode_text)
            print(f"✅ Successfully generated episode with {len(episode_data)} topics")

            # Create a new entry in the episode table
            episode_insert_data = {
                "episode": episode_text,  # Store the full JSON response
                "newsletter_emails": unique_emails,  # List of unique emails
                "user_id": user_id,  # User ID passed to the function
            }

            # Insert the new episode record
            episode_result = (
                await supabase_func_instance.supabase.table("episodes")
                .insert(episode_insert_data)
                .execute()
            )
            mail_manager.reduce_bg_task(user_id)

            # Check if the insert was successful
            if episode_result.data:
                episode_id = episode_result.data[0]["id"]
                print(f"✅ Successfully created episode with ID: {episode_id}")

                if final_process:
                    response = await supabase_func_instance.updateProfileData(
                        table_name="profiles",
                        user_id=user_id,
                        columnName="episode_processing",
                        value=True,
                    )
                    if response:
                        print("Profile flag updated")

                    mail_manager.delete_all_counts(user_id)

                    print("🔴🔴🔴 Last processing inside the  create_episode_with_llm")
                    return {
                        "success": True,
                        "episode_id": episode_id,
                        "email_count": len(unique_emails),
                    }

                task = mail_manager.get_bg_task(user_id)
                print("Task Number", task)

                # if task > 0:
                #     mail_manager.set_kill_owner(user_id)
                # else:
                final_process = mail_manager.compare_webhook_email(user_id)
                if final_process:
                    owner = mail_manager.get_kill_owner(user_id)
                    if owner:
                        response = await supabase_func_instance.updateProfileData(
                            table_name="profiles",
                            user_id=user_id,
                            columnName="episode_processing",
                            value=True,
                        )
                    if response:
                        print("Profile flag updated")

                    mail_manager.delete_all_counts(user_id)
                    mail_manager.delete_kill_owner(user_id)

                    print("🔴🔴🔴 Last processing inside the  create_episode_with_llm")

                    return {
                        "success": True,
                        "episode_id": episode_id,
                        "email_count": len(unique_emails),
                    }
                else:
                    return {
                        "success": True,
                        "episode_id": episode_id,
                        "email_count": len(unique_emails),
                    }

            else:
                print("❌ Failed to insert episode record")
                return {"success": False, "error": "Failed to insert episode record"}

        except json.JSONDecodeError as json_err:
            print(f"❌ Error: LLM didn't return valid JSON: {json_err}")
            print(f"Raw LLM response: {episode_text}")
            return {
                "success": False,
                "error": f"Invalid JSON response from LLM: {str(json_err)}",
            }

    except Exception as e:
        print(f"❌ Error processing episode with LLM: {str(e)}")
        raise


async def process_episode_limits(records, user_id):
    """
    Background task to process episode limits and update flags.
    This function runs independently of the HTTP request/response cycle.
    """
    from utils.supabaseUtils import supabase_func_instance

    try:
        # Get all record IDs from the incoming webhook data
        all_record_ids = [r["id"] for r in records]

        # STEP 1: Filter out records that are already being processed
        async with processing_lock:
            # Clean up old processing records (older than 5 minutes)
            current_time = time.time()
            for rid in list(processing_records.keys()):
                if processing_records[rid]["timestamp"] < current_time - 300:
                    del processing_records[rid]

            # Filter out records that are already being processed
            available_record_ids = []
            for rid in all_record_ids:
                if rid not in processing_records:
                    # Mark as being processed
                    processing_records[rid] = {
                        "timestamp": current_time,
                        "status": "processing",
                    }
                    available_record_ids.append(rid)
                else:
                    print(f"Skipping record {rid} - already being processed")

        if not available_record_ids:
            print("All records are already being processed")
            return

        # STEP 2: Check the database to filter out records that already have episode_flag=True
        try:
            result = (
                await supabase_func_instance.supabase.table("user_news_letters")
                .select("id, episode_flag, token_count, sent_time")
                .in_("id", available_record_ids)
                .execute()
            )

            # Filter records that don't have episode_flag set to True
            eligible_records = []
            for record in result.data:
                if not record.get("episode_flag", False):
                    eligible_records.append(record)
                else:
                    print(
                        f"Skipping record {record['id']} - already has episode_flag=True"
                    )
                    # Release the processing lock for this record
                    async with processing_lock:
                        if record["id"] in processing_records:
                            del processing_records[record["id"]]

            if not eligible_records:
                print("No eligible records found after filtering")
                return

        except Exception as e:
            print(f"Error checking database flags: {e}")
            # Release all locks on error
            async with processing_lock:
                for rid in available_record_ids:
                    if rid in processing_records:
                        del processing_records[rid]
            return

        # STEP 3: Sort eligible records by date (newest first)
        sorted_records = sorted(
            eligible_records, key=lambda r: r.get("sent_time", ""), reverse=True
        )

        # STEP 4: Apply your business logic for token limits
        total_token_count = sum(r.get("token_count", 0) for r in sorted_records)

        # Case 1: If the total token count is less than 3500
        if total_token_count < 3500:
            if len(sorted_records) >= 3:
                record_ids_to_update = [r["id"] for r in sorted_records]
                print(
                    f"Updating episode flags for {len(record_ids_to_update)} records with total token count {total_token_count}"
                )
                # await updateFlag(record_ids_to_update, supabase_func_instance)
                await create_episode_with_llm(records, record_ids_to_update, user_id)

                # Mark as completed in our tracking
                async with processing_lock:
                    for rid in record_ids_to_update:
                        if rid in processing_records:
                            processing_records[rid]["status"] = "completed"

                return {"record_ids": record_ids_to_update}
            else:
                print("Not enough records to create the episodes (need at least 3)")
                # Release the processing locks
                async with processing_lock:
                    for r in sorted_records:
                        if r["id"] in processing_records:
                            del processing_records[r["id"]]

                final_process = mail_manager.compare_webhook_email(user_id)

                if final_process:
                    task = mail_manager.get_bg_task(user_id)
                    print(task, "Outside LLM Episode function")
                    if task > 0:
                        mail_manager.set_kill_owner(user_id)
                    else:
                        response = await supabase_func_instance.updateProfileData(
                            table_name="profiles",
                            user_id=user_id,
                            columnName="episode_processing",
                            value=True,
                        )
                        if response:
                            print("Profile flag updated")

                        mail_manager.delete_all_counts(user_id)
                        print(
                            "🔴🔴🔴 Last processing outside the  create_episode_with_llm"
                        )
                else:
                    print("🟢🟢🟢 Still going")
                return

        # Case 2: If token count exceeds 3500, drop newest records one by one
        records_to_process = sorted_records.copy()
        records_to_skip = []

        while total_token_count > 3500 and records_to_process:
            # Remove the newest record
            if len(records_to_process) == 1:
                break

            skipped_record = records_to_process.pop(0)
            records_to_skip.append(skipped_record["id"])
            total_token_count = sum(r.get("token_count", 0) for r in records_to_process)

        # Release locks for skipped records
        async with processing_lock:
            for rid in records_to_skip:
                if rid in processing_records:
                    del processing_records[rid]

        # After dropping records, check if we have enough
        if total_token_count < 3500:
            if len(records_to_process) >= 1:
                record_ids_to_update = [r["id"] for r in records_to_process]
                print(
                    f"After dropping {len(records_to_skip)} records, updating episode flags for {len(record_ids_to_update)} records"
                )
                # await updateFlag(record_ids_to_update, supabase_func_instance)
                await create_episode_with_llm(records, record_ids_to_update, user_id)

                # Mark as completed
                async with processing_lock:
                    for rid in record_ids_to_update:
                        if rid in processing_records:
                            processing_records[rid]["status"] = "completed"

                return {"record_ids": record_ids_to_update}
            else:
                print("Not enough records to create the episodes after filtering")
        else:
            print("Could not reduce token count below 3500")

        final_process = mail_manager.compare_webhook_email(user_id)
        if final_process:
            task = mail_manager.get_bg_task(user_id)
            if task > 0:
                mail_manager.set_kill_owner(user_id)
            else:
                response = await supabase_func_instance.updateProfileData(
                    table_name="profiles",
                    user_id=user_id,
                    columnName="episode_processing",
                    value=True,
                )
                if response:
                    print("Profile flag updated")

                mail_manager.delete_all_counts(user_id)
                print("🔴🔴🔴 Last processing outside the  create_episode_with_llm")
        else:
            print("🟢🟢🟢 Still going")
        # Release any remaining locks if we didn't process

        async with processing_lock:
            for r in records_to_process:
                if r["id"] in processing_records:
                    del processing_records[r["id"]]

    except Exception as e:
        print(f"❌ Error in process_episode_limits: {str(e)}")
        # Release all locks on error
        try:
            async with processing_lock:
                for rid in all_record_ids:
                    if rid in processing_records:
                        del processing_records[rid]
        except Exception as cleanup_error:
            print(f"Error while cleaning up locks: {cleanup_error}")


async def updateFlag(record_ids, func_instance):
    """Update episode flags for the given record IDs"""
    try:
        # We've already filtered the records, so just update all of them
        await func_instance.supabase.table("user_news_letters").update(
            {"episode_flag": True}
        ).in_("id", record_ids).execute()

        print(f"✅ Successfully updated episode flags for {len(record_ids)} records")

    except Exception as e:
        print(f"❌ Error updating records: {e}")

        # Release the processing locks for these records
        async with processing_lock:
            for rid in record_ids:
                if rid in processing_records:
                    del processing_records[rid]

        raise HTTPException(status_code=500, detail="Failed to update records")


async def process_text_with_llm(record_id: str, parsed_text: str, user_id: str):
    """
    Background task to process text with LLM and update the database.
    This function runs independently of the HTTP request/response cycle.
    """
    from utils.supabaseUtils import supabase_func_instance

    max_retries = 3
    try:
        # Format the prompt and prepare history
        formatted_prompt = prompt.format(
            parsed_text=parsed_text,
        )
        history = [
            {
                "role": "system",
                "content": formatted_prompt,
            }
        ]

        # Call the OpenAI model
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history,
            temperature=0,
        )

        refined_text = response.choices[0].message.content.strip()
        token = count_tokens(refined_text)
        print(f"Token count: {token}")

        update_data = {"refined_text": refined_text, "token_count": token}
        for attempt in range(max_retries):

            result = (
                await supabase_func_instance.supabase.table("user_news_letters")
                .update(update_data)
                .eq("id", record_id)
                .execute()
            )
            # Check if there is at least one row in "data"
            if len(result.data) > 0:
                # We successfully updated at least one row, so break out
                print(f"Row updated on attempt #{attempt+1}")
                break
            else:
                print(f"No row updated on attempt #{attempt+1}... retrying...")
                await asyncio.sleep(0.5)

        # Check if the result indicates success
        if result:
            print(
                f"✅ Refine Text Update successful: {record_id} \n {result} \n {update_data}"
            )
        else:
            print(result)

    except Exception as e:
        mail_manager.reduce_user_mail(userID=user_id)
        print(f"❌ Failed to update record {record_id}: {e}")
        traceback.print_exc()
