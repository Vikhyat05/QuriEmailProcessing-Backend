from fastapi import FastAPI, WebSocketDisconnect, WebSocket, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
import requests
from router.gmailAuth import auth_router
from router.fetchSender import email_router
from router.aiProcessing import ai_router
from utils.supabaseUtils import (
    init_global_instance,
    supabase_func_instance,
    SupaBaseFunc,
    fetchEpisodes,
)
from fastapi.responses import JSONResponse

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """Ensure Supabase clients are initialized when FastAPI starts."""
    await init_global_instance()
    print("✅ Supabase global instance created!")


app.include_router(auth_router)
app.include_router(email_router, prefix="/email")
app.include_router(ai_router, prefix="/ai")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"],
    allow_credentials=True,
)


# @app.get("/get_episodes")
# async def get_notes(Authorization: str = Header(...)):
#     """
#     Fetch all notes for the user based on access token.
#     """

#     # Extract the Bearer token
#     print(Authorization)
#     if not Authorization.startswith("Bearer "):
#         raise HTTPException(status_code=400, detail="Invalid token format")

#     access_token = Authorization.split(" ")[1]
#     supabase_response = fetchEpisodes(access_token=access_token)

#     if not supabase_response:
#         return JSONResponse(
#             content=None,
#             status_code=400,
#         )

#     return JSONResponse(
#         content=supabase_response,
#         status_code=200,
#     )


# @app.get("/auth/emails")
def fetch_latest_emails(access_token):
    """
    1) Exchange the code for a session to get the user's Google access token.
    2) Make a request to the Gmail API to fetch top 5 email subject lines.
    """

    try:
        messages_res = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"maxResults": 5},  # top 5
            timeout=10,
        )
        messages_res.raise_for_status()

        messages_data = messages_res.json()
        messages = messages_data.get("messages", [])

        subject_lines = []
        for msg in messages:
            msg_id = msg["id"]
            # Get individual message metadata to retrieve Subject
            detail_res = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "metadataHeaders": ["Subject"]},
                timeout=10,
            )
            detail_res.raise_for_status()
            detail_data = detail_res.json()

            headers = detail_data.get("payload", {}).get("headers", [])
            # Extract the Subject header
            subject_line = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
            )
            subject_lines.append(subject_line)

        return {"emails": subject_lines}

    except requests.RequestException as re:
        raise HTTPException(status_code=400, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching emails: {str(e)}")
