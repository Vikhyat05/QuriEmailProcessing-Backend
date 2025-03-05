async def save_emails_batch(user_id: str, emails: list):
    """Insert emails into Supabase in batches of 5 while avoiding duplicates."""

    if not emails:
        return {"status": "error", "message": "No emails provided."}

    print("inside the save_emails_batch 1")

    batch_size = 5
    buffer_batch = []
    total_inserted = 0
    failed_batches = []
    # print(emails)
    print("Batch count is ", len(emails))

    for email in emails:
        email["user_id"] = user_id  # Attach user_id
        buffer_batch.append(email)

        if len(buffer_batch) == batch_size:
            response = await upsert_emails(buffer_batch)
            # response = upsert_emails(buffer_batch)

            if response.get("status") == "success":
                total_inserted += len(buffer_batch)
                buffer_batch.clear()  # Clear buffer after successful insert
            else:
                failed_batches.append(
                    {"batch": buffer_batch, "error": response.get("error_details")}
                )
                buffer_batch.clear()  # Clear buffer even on failure to prevent duplicate inserts

    print("inside the save_emails_batch 2")
    # Insert any remaining emails
    if buffer_batch:
        response = await upsert_emails(buffer_batch)
        # response = upsert_emails(buffer_batch)
        print("This is the response on upsert ", response)

        if response.get("status") == "success":
            total_inserted += len(buffer_batch)
        else:
            failed_batches.append(
                {"batch": buffer_batch, "error": response.get("error_details")}
            )

    # Return a structured summary
    if failed_batches:
        print("inside the save_emails_batch 3")
        return {
            "status": "partial_success",
            "message": f"Inserted {total_inserted} emails, but some batches failed.",
            "failed_batches": failed_batches,
        }
    else:

        return {
            "status": "success",
            "message": f"Successfully inserted {total_inserted} emails.",
        }


async def upsert_emails(batch: list):
    from utils.supabaseUtils import supabase_func_instance

    """Upserts emails into the 'user_news_letters' table, avoiding duplicates."""
    print("Length of the batch", len(batch))
    try:
        response = (
            await supabase_func_instance.supabase.schema("public")
            .table("user_news_letters")
            .upsert(batch, on_conflict="user_id,email_address,subject")
            .execute()
        )

        # print("This is supabase response:", response)

        # Check if response contains 'data'
        if "data" in response and response["data"]:
            print(
                {
                    "status": "success",
                    "message": f"✅ {len(response['data'])} records inserted/updated successfully.",
                    # "data": response["data"],
                }
            )
            return {
                "status": "success",
                "message": f"✅ {len(response['data'])} records inserted/updated successfully.",
                "data": response["data"],
            }
        elif "error" in response and response["error"]:
            print(
                {
                    "status": "error",
                    "message": "Error inserting/updating records.",
                    # "error_details": response["error"],
                }
            )
            return {
                "status": "error",
                "message": "Error inserting/updating records.",
                # "error_details": response["error"],
            }
        else:
            print(
                {
                    "status": "error",
                    "message": "Unexpected response format from Supabase.",
                    # "raw_response": response,
                }
            )
            return {
                "status": "error",
                "message": "Unexpected response format from Supabase.",
                # "raw_response": response,
            }

    except Exception as e:
        return {
            "status": "error",
            "message": "Exception occurred while inserting/updating records.",
            "error_details": str(e),
        }
