from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fastapi.responses import RedirectResponse, JSONResponse
import os
from fastapi import HTTPException
from pydantic import BaseModel
import requests
from utils.encryption import cryption
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from utils.supabaseUtils import SupaBaseFunc


auth_router = APIRouter()
load_dotenv()
IOS_REDIRECT_URI = "myapp://oauthredirect"
GMAIL_SCOPES = "https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/gmail.readonly"


client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@auth_router.get("/auth/login")
async def google_login(request: Request):
    """
    Redirect user to Google Sign-In using Supabase OAuth with Gmail scopes.
    """
    # from utils.supabaseUtils import supabaseAnon, SupaBaseFunc
    from utils.supabaseUtils import supabase_func_instance

    print(supabase_func_instance)
    if supabase_func_instance is None:
        raise HTTPException(
            status_code=500, detail="SupabaseAnon is still None. Initialization failed."
        )

    user_agent = request.headers.get("User-Agent", "").lower()

    # redirect_uri = "qurimail://oauthredirect"
    redirect_uri = "myapp://oauthredirect"
    try:
        response = await supabase_func_instance.supabaseAnon.auth.sign_in_with_oauth(
            {
                "provider": "google",
                "options": {
                    "redirect_to": redirect_uri,
                    "scopes": GMAIL_SCOPES,  # ✅ Correctly defined Gmail scopes
                    "query_params": {
                        "access_type": "offline",
                        "prompt": "consent",
                    },
                },
            }
        )
        print("This is Response", response)
        print(response.url)  # Debugging: Check if URL is correct
        return RedirectResponse(response.url)  # ✅ Fix applied: Use `.url`
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google Auth failed: {str(e)}")


@auth_router.get("/auth/callback")
async def google_callback(request: Request):
    """
    Handles OAuth callback and exchanges the authorization code for a session.
    """
    from utils.supabaseUtils import supabase_func_instance

    # global provider_tokens
    code = request.query_params.get("code")  # Get 'code' from query parameters
    print(f"Received Code: {code}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is missing")

    try:
        # Exchange the authorization code for a session
        auth_response = (
            await supabase_func_instance.supabaseAnon.auth.exchange_code_for_session(
                {"auth_code": code}
            )
        )

        # print("Auth Response:", auth_response)

        if auth_response is None:
            raise HTTPException(status_code=400, detail="Supabase response is None")

        # Extract user object safely
        user = getattr(auth_response, "user", None)
        session = getattr(auth_response, "session", None)

        if not user:
            raise HTTPException(
                status_code=400, detail="Failed to retrieve user from session"
            )

        # Extract user metadata safely
        user_metadata = getattr(user, "user_metadata", {})

        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user_metadata.get("full_name", "Unknown User"),
            "avatar_url": user_metadata.get("avatar_url", ""),
            "google_access_token": session.provider_token,
            "google_refresh_token": session.provider_refresh_token,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        }

        print("The REfresh Token", user_data["refresh_token"])
        print("The ACCess Token", user_data["google_access_token"])
        userID = user_data["id"]
        google_access_token = user_data["google_access_token"]
        envrypted_access_token = cryption.encrypt_token(google_access_token)

        google_refresh_token = user_data["google_refresh_token"]
        envrypted_refresh_token = cryption.encrypt_token(google_refresh_token)

        # 1️⃣ Check if user exists in "profiles" table
        senderSelected = await supabase_func_instance.sender_selcted_check(userID)
        print(senderSelected)
        if senderSelected:
            senderSelectedFlag = True
        else:
            senderSelectedFlag = False

        user_data["senderSelected"] = senderSelectedFlag

        data = {
            "user_id": userID,
            "provider": "Google",
            "access_token": envrypted_access_token,
            "refresh_token": envrypted_refresh_token,
        }

        print(data)

        try:
            response = await supabase_func_instance.upsert_into_table(
                "userGmailToken", data, "user_id"
            )
        except Exception as e:
            print("Not able to add tokens", e)
            print(f"Error during authentication: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error during authentication: {str(e)}"
            )

        if response is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to update/insert user token into Supabase",
            )

        if senderSelectedFlag:
            print("Show the home view directly")
        else:
            print("Show case the selecter window")

        return JSONResponse(
            content={"message": "User authenticated", "user": user_data},
            status_code=200,
        )

    except Exception as e:
        print(f"Error during authentication: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error during authentication: {str(e)}"
        )


@auth_router.post("/auth/refresh")
def refresh_google_access_token(request: RefreshTokenRequest) -> dict:
    """Exchanges Google refresh token for a new access token."""

    # Replace with your actual Google Client ID and Secret
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": request.refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(url, data=data)
    token_info = response.json()
    print("This is google_token_response", response)

    return JSONResponse(
        content=token_info,
        status_code=200,
    )
