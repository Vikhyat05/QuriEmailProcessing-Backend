from utils.aiProcessingUtils import (
    process_episode_limits,
    process_text_with_llm,
)
from fastapi import APIRouter, HTTPException, Request
from fastapi import BackgroundTasks, Request, HTTPException
from utils.mailManager import mail_manager

ai_router = APIRouter()


@ai_router.post("/episodeLimitCheck")
async def episodeLimitCheck(request: Request, background_tasks: BackgroundTasks):
    """
    This endpoint is triggered when Supabase creates a new entry in the table.
    It immediately acknowledges the webhook and handles the processing in a background task.
    """
    try:
        data = await request.json()
        user_id = data.get("user_id")
        records = data.get("records", [])

        mail_manager.update_webhook_count(userID=user_id)

        if not records:
            return {"message": "No records provided"}

        print(f"🔔 Received webhook for episodeLimitCheck with {len(records)} records")

        # Start background task
        background_tasks.add_task(
            process_episode_limits, records=records, user_id=user_id
        )  # Checks the episode limit crieteria and generate episode if conditions meet

        return {
            "status": "processing",
            "message": "Episode limit check started in background",
        }

    except Exception as e:
        print(f"Error in episodeLimitCheck handler: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@ai_router.post("/refineText")
async def refineText(request: Request, background_tasks: BackgroundTasks):
    """
    This endpoint is triggered by Supabase when a new row is inserted.
    It immediately acknowledges the webhook and processes the LLM request
    in a background task to avoid timeout errors.
    """
    try:
        # Parse the incoming JSON payload
        data = await request.json()
        record_id = data.get("id")
        user_id = data.get("user_id")
        parsed_text = data.get("parsed_text")

        if not (record_id and parsed_text):
            raise HTTPException(
                status_code=400, detail="Missing required fields: id or parsed_text"
            )

        print(f"🔔 Received webhook from Supabase: {record_id}")

        # Add the LLM processing to a background task
        background_tasks.add_task(
            process_text_with_llm,
            record_id=record_id,
            parsed_text=parsed_text,
            user_id=user_id,
        )

        # Immediately return a success response to Supabase
        return {
            "status": "processing",
            "message": "Text refinement started in background",
        }

    except Exception as e:
        print(f"Error in webhook handler: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
