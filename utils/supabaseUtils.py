import os
from supabase import create_client, Client
from postgrest import APIError
from dotenv import load_dotenv
from supabase import acreate_client, AsyncClient


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
print("The new URL", SUPABASE_URL)
supabaseSync: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
supabaseAnonSync: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def fetchEpisodes(access_token):

    supabaseAnonSync.postgrest.session.headers.update(
        {"Authorization": f"Bearer {access_token}"}
    )

    supabase_response = supabaseAnonSync.table("episodes").select("*").execute()
    # supabase_response = (
    #     supabase.table("NotesFunctionCall").select("*").eq("userID", user_id).execute()
    # )

    return supabase_response.data


# supabase: AsyncClient = None
# supabaseAnon: AsyncClient = None


# async def init_supabase():
#     global supabase, supabaseAnon  # Ensure we're modifying global variables

#     print(f"🔹 Loading Supabase with URL: {SUPABASE_URL}")
#     print(f"🔹 Loading Supabase with ANON KEY: {SUPABASE_ANON_KEY}")

#     if not SUPABASE_URL or not SUPABASE_ANON_KEY:
#         print("❌ ERROR: Missing Supabase environment variables!")
#         return  # Exit early if env variables are not set

#     supabase = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
#     supabaseAnon = await acreate_client(SUPABASE_URL, SUPABASE_ANON_KEY)

#     print(f"✅ Supabase clients initialized: supabaseAnon = {supabaseAnon}")


# async def init_supabase():
#     global supabase, supabaseAnon
#     supabase = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
#     supabaseAnon = await acreate_client(SUPABASE_URL, SUPABASE_ANON_KEY)
#     print("✅ Supabase clients initialized successfully.")


# supabase: AsyncClient = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
# supabaseAnon: AsyncClient = await acreate_client(SUPABASE_URL, SUPABASE_ANON_KEY)


class SupaBaseFunc:
    def __init__(self, supabase: AsyncClient, supabaseAnon: AsyncClient):
        self.supabase = supabase
        self.supabaseAnon = supabaseAnon

    @classmethod
    async def create(cls):
        """Asynchronously initialize Supabase clients and return an instance."""
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise ValueError("❌ Missing Supabase environment variables!")

        print("🔹 Initializing Supabase clients...")
        supabase = await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        supabaseAnon = await acreate_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✅ Supabase clients initialized!")

        return cls(supabase, supabaseAnon)

    async def sender_selcted_check(self, user_id: str):
        try:
            response = (
                await self.supabase.table("profiles")
                .select("slected_senders")  # Select only the Flag column
                .eq("id", user_id)  # Filter by user ID
                .single()
                .execute()
            )

            if response.data:
                return response.data.get("slected_senders")
            return None
        except Exception as e:
            print(f"Error fetching flag value: {e}")
            return None

    async def getUserId(self, accessToken):
        token = accessToken
        try:
            supabase_response = await self.supabaseAnon.auth.get_user(token)
            userId = supabase_response.user.id
            return {"status": "verified", "UserID": userId}

        except Exception as e:
            error_message = str(e)
            if "token is expired" in error_message:
                return {
                    "status": "error",
                    "error": "token_expired",
                    "message": "Token has expired. Please refresh.",
                }

            else:
                return {
                    "status": "error",
                    "error": "authentication_failed",
                    "message": error_message,
                }

    async def updateProfileData(self, table_name, user_id, columnName, value):

        try:
            response = (
                await self.supabase.table(table_name)
                .update({columnName: value})
                .eq("id", user_id)
                .execute()
            )
            return response
        except APIError as e:
            print(f"Supabase API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    async def upsert_into_table(self, table_name: str, data: dict, unique_column: str):
        """
        Inserts a new row if `unique_column` does not exist, otherwise updates the existing row.

        :param table_name: The name of the table.
        :param data: A dictionary containing the data to insert/update.
        :param unique_column: The column that should be unique (e.g., "userID").
        :return: The response from Supabase API.
        """
        try:
            response = (
                await self.supabase.table(table_name)
                .upsert(data, on_conflict=[unique_column])
                .execute()
            )
            return response
        except APIError as e:
            print(f"Supabase API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    @staticmethod
    async def insert_into_table(self, table_name: str, data: dict):
        """
        Inserts a row into the specified Supabase table.

        :param table_name: The name of the table to insert data into.
        :param data: A dictionary where keys are column names and values are the corresponding values.
        :return: The response from Supabase API.
        """

        try:
            response = await self.supabase.table(table_name).insert(data).execute()
            return response
        except APIError as e:
            print(f"Supabase API Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    async def fetchNotes(self, access_token):
        self.supabaseAnon.postgrest.session.headers.update(
            {"Authorization": f"Bearer {access_token}"}
        )

        try:
            notesData = (
                await self.supabase.table("NotesFunctionCall")
                .select("*")  # ✅ No need to filter by userID explicitly
                .execute()
            )
            return notesData
        except APIError as e:
            print(f"Supabase API Error: {e}")
        return None


supabase_func_instance: SupaBaseFunc | None = None


async def init_global_instance():
    """
    Create the global instance if it doesn't exist already.
    This is what you will call exactly once on startup.
    """
    global supabase_func_instance
    if supabase_func_instance is None:
        supabase_func_instance = await SupaBaseFunc.create()
    return supabase_func_instance
