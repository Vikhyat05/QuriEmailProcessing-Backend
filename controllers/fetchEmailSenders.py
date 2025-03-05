import requests
import email.utils
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, AsyncGenerator
import os
from dotenv import load_dotenv
import json
from collections import OrderedDict


load_dotenv()
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_URL = "https://www.googleapis.com/gmail/v1/users/me/messages"

client_id = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")


class FetchEmailSenders:
    def __init__(self):
        self.global_senders = OrderedDict()  # ✅ Maintains order of first appearance
        self.global_unique_emails = set()  # ✅ Tracks all encountered emails
        self.sent_senders = set()  # ✅ Tracks emails already sent to frontend
        self.SENTINEL = object()

        # self.global_senders: Dict[str, str] = {}
        # self.global_unique_emails = set()

    async def process_messages(self, access_token: str, message_ids: List[str]):
        """Process a batch of messages and store sender data."""
        headers = {"Authorization": f"Bearer {access_token}"}

        for msg_id in message_ids:
            msg_url = f"{GMAIL_API_URL}/{msg_id}"
            msg_response = requests.get(msg_url, headers=headers)
            if msg_response.status_code != 200:
                continue  # Skip failed requests

            msg_data = msg_response.json()
            payload = msg_data.get("payload", {})
            msg_headers = payload.get("headers", [])

            for header in msg_headers:
                if (
                    isinstance(header, dict)
                    and header.get("name", "").lower() == "from"
                ):
                    sender_name, sender_email = email.utils.parseaddr(
                        header.get("value", "")
                    )
                    if not sender_email or sender_email in self.global_unique_emails:
                        continue
                    if not sender_name:
                        sender_name = sender_email

                    # Ensure unique sender names
                    # Ensure we keep the first occurrence and ignore duplicates
                    if sender_email not in self.global_unique_emails:
                        self.global_senders[sender_name] = (
                            sender_email  # First occurrence is stored
                        )
                        self.global_unique_emails.add(sender_email)  # Track seen emails

    async def fetch_message_ids(
        self, access_token: str, query: str, message_queue: asyncio.Queue
    ):
        """Fetch message IDs and add them to the queue."""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"q": query}

        while True:
            response = requests.get(GMAIL_API_URL, headers=headers, params=params)
            if response.status_code != 200:
                print("Error fetching messages:", response.text)
                return

            data = response.json()
            print("Data")  # ✅ Prints fetched messages

            if "messages" in data:
                message_ids = [msg["id"] for msg in data["messages"]]
                for msg_id in message_ids:
                    await message_queue.put(msg_id)  # ✅ Store message IDs in the queue
            else:
                break  # No more messages

            next_page = data.get("nextPageToken")
            if next_page:
                params["pageToken"] = next_page
            else:
                break

    async def process_batches(
        self,
        access_token: str,
        message_queue: asyncio.Queue,
        stream_queue: asyncio.Queue,
    ):
        """Process messages in batches of 10 and send updates."""

        while True:
            batch_size = min(1, message_queue.qsize())  #  Get batch size dynamically
            if batch_size == 0:
                break  #  Stop when queue is empty

            batch = await asyncio.gather(
                *(message_queue.get() for _ in range(batch_size))
            )
            await self.process_messages(access_token, batch)

            # Extract senders from global_senders (current known senders)
            current_batch_senders = OrderedDict()
            for sender_name, sender_email in self.global_senders.items():
                if sender_email not in self.sent_senders:
                    current_batch_senders[sender_name] = sender_email
                    self.sent_senders.add(sender_email)

            if current_batch_senders:
                await stream_queue.put(json.dumps({"senders": current_batch_senders}))
        # ✅ Signal completion by placing sentinel in stream_queue
        await stream_queue.put(self.SENTINEL)

    async def stream_all_messages(self, access_token: str) -> AsyncGenerator[str, None]:
        now = datetime.now(timezone.utc)
        last_7_days = now - timedelta(days=1)
        query = f"after:{int(last_7_days.timestamp())} category:primary"

        message_queue = asyncio.Queue(maxsize=100)
        stream_queue = asyncio.Queue()

        async def send_stream_updates():
            """Continuously yield new updates as they arrive in stream_queue."""
            while True:
                update = await stream_queue.get()
                if update is self.SENTINEL:
                    break
                yield f"data: {update}\n\n"

        fetch_task = asyncio.create_task(
            self.fetch_message_ids(access_token, query, message_queue)
        )
        process_task = asyncio.create_task(
            self.process_batches(access_token, message_queue, stream_queue)
        )

        async for update in send_stream_updates():
            yield update  # ✅ Send updates live to the frontend

        await asyncio.gather(fetch_task, process_task)

        print("DOONEE")
        yield "data: [DONE]\n\n"
