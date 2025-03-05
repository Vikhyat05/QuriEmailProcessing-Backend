from fastapi import Header


async def get_current_user(supabase_access_token: str = Header(...)) -> str:
    from utils.supabaseUtils import supabase_func_instance

    """Verifies Supabase access token and retrieves user_id."""
    print("This is the access token", supabase_access_token)
    response = await supabase_func_instance.getUserId(accessToken=supabase_access_token)
    userid = response["UserID"]
    return userid
