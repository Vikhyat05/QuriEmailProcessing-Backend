from fastapi import Query
from fastapi.responses import StreamingResponse
from fastapi import Depends, APIRouter, Header, HTTPException, Request
from controllers.fetchEmailSenders import FetchEmailSenders
from pydantic import BaseModel
from typing import Dict
from controllers.fetchEmailContent import EmailContentFetcher
from utils.saveEmailUtil import save_emails_batch
import asyncio
from Middleware.authMiddleware import get_current_user

email_router = APIRouter()


# Define request model
class EmailSendersRequest(BaseModel):
    Dict[str, str]


@email_router.get("/senders", response_class=StreamingResponse)
async def stream_email_senders_endpoint(
    google_access_token: str = Query(..., description="Google API Access Token"),
    # user_access_token: str = Query(
    #     ..., description="User's login token for validation"
    # ),
):
    """Streams email senders in real-time as they are fetched."""

    email_fetcher = FetchEmailSenders()
    # Here, you can validate `user_access_token` if necessary

    # Return an SSE response using the generator function
    return StreamingResponse(
        email_fetcher.stream_all_messages(google_access_token),
        media_type="text/event-stream",
    )


@email_router.post("/send_selected")
async def send_selected(
    request: Request,
    senders: Dict[str, str],
    user_id: str = Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization")

    print("This is the user id", user_id)

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    google_access_token = auth_header.split("Bearer ")[1]
    print("This is the google access token", google_access_token)

    contentFetcher = EmailContentFetcher(
        access_token=google_access_token, user_id=user_id
    )

    # Run blocking fetch function in an async-friendly way
    try:
        emails = await asyncio.to_thread(contentFetcher.fetch_recent_emails, senders)

        # print("Fetched email results:", emails)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")

    # Save emails asynchronously
    try:
        await save_emails_batch(user_id, emails)
        # save_emails_batch(user_id, emails)
        # await asyncio.to_thread(save_emails_batch, user_id, emails)
        print("Saves the content")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save emails: {str(e)}")

    return {"message": "Data received successfully"}
