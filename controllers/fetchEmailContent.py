import requests
import datetime
import base64
from typing import List, Dict
from bs4 import BeautifulSoup  # for HTML-to-text conversion
import re
import unicodedata
from email.utils import parsedate_to_datetime
from utils.mailManager import mail_manager

GMAIL_API_URL = "https://www.googleapis.com/gmail/v1/users/me/messages"


class EmailContentFetcher:
    def __init__(self, access_token: str, user_id):
        self.access_token = access_token
        self.userId = user_id

    def clean_text(self, text: str) -> str:
        """Normalize and remove unwanted invisible/whitespace characters."""
        # Normalize Unicode characters (this can help convert compatibility characters)
        text = unicodedata.normalize("NFKC", text)

        # Define a set of unwanted characters: non-breaking space, zero-width spaces, etc.
        unwanted_chars = "".join(
            [
                "\u00A0",  # non-breaking space
                "\u200B",  # zero width space
                "\u200C",  # zero width non-joiner
                "\u200D",  # zero width joiner
                "\uFEFF",  # zero width no-break space
            ]
        )

        # Replace each unwanted character with a normal space
        text = re.sub(f"[{re.escape(unwanted_chars)}]", " ", text)

        # Collapse multiple whitespace characters into a single space and strip leading/trailing spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def fetch_recent_emails(self, senders: Dict[str, str]) -> List[Dict[str, str]]:
        """Fetches recent emails from specific senders within the last 7 days."""
        try:
            now = datetime.datetime.utcnow()
            seven_days_ago = now - datetime.timedelta(days=1)
            formatted_date = seven_days_ago.strftime("%Y/%m/%d")

            # Extract only email addresses from dict values
            email_list = list(senders.values())
            from_query = " OR ".join(email_list)
            query = f"from:({from_query}) after:{formatted_date} category:primary"

            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "q": query,
                "format": "metadata",
            }  # 'format=metadata' for lighter fetch

            response = requests.get(GMAIL_API_URL, headers=headers, params=params)
            if response.status_code != 200:
                print("Error fetching messages:", response.text)
                return []

            data = response.json()
            if "messages" not in data:
                return []

            # Now fetch the full content of each message ID
            emails_data = []

            for message in data["messages"]:
                email_data = self.fetch_email_content(message["id"])
                if email_data:
                    emails_data.append(email_data)

            unique_emails = self.remove_duplicates_by_subject(emails_data)

            print("Total Emails", len(unique_emails))

            mail_manager.set_user_mails(
                userID=self.userId, mailCount=len(unique_emails)
            )

            return unique_emails

        except Exception as error:
            print(f"An error occurred: {error}")
            return []

    def remove_duplicates_by_subject(self, emails):
        """
        Removes duplicate dictionaries from the 'emails' list
        if they share the same 'subject'.

        Returns a new list containing only the first occurrence
        of each unique subject.
        """
        seen_subjects = set()
        unique_emails = []

        for entry in emails:
            subj = entry.get("subject")
            if subj not in seen_subjects:
                unique_emails.append(entry)
                seen_subjects.add(subj)

        return unique_emails

    def fetch_email_content(self, message_id: str) -> Dict[str, str]:
        """Fetch full email content using Gmail 'full' format."""
        url = f"{GMAIL_API_URL}/{message_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"format": "full"}  # Request the full message with all parts

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print("Error fetching email:", response.text)
            return {}

        msg = response.json()

        # Extract headers
        headers_list = msg["payload"]["headers"]
        sender_email = next(
            (h["value"] for h in headers_list if h["name"] == "From"), None
        )
        sent_time_raw = next(
            (h["value"] for h in headers_list if h["name"] == "Date"), None
        )
        subject = next(
            (h["value"] for h in headers_list if h["name"] == "Subject"), None
        )

        # Convert 'Date' to required format
        sent_time_formatted = None
        if sent_time_raw:
            parsed_datetime = parsedate_to_datetime(
                sent_time_raw
            )  # Convert to datetime
            parsed_datetime = parsed_datetime.astimezone()  # Ensure it's timezone-aware
            sent_time_formatted = parsed_datetime.strftime("%Y-%m-%d %H:%M:%S.%f%z")

        # Extract the message text (plain or HTML)
        email_body = self.extract_email_text(msg)
        print("id", message_id, " subject", subject)

        return {
            "email_address": sender_email,
            "subject": subject,
            "parsed_text": email_body,
            "sent_time": sent_time_formatted,  # Now in the format you requested
        }

    # def fetch_email_content(self, message_id: str) -> Dict[str, str]:
    #     """Fetch full email content using Gmail 'full' format."""
    #     url = GMAIL_API_URL + f"/{message_id}"
    #     # f"https://www.googleapis.com/gmail/v1/users/me/messages/{message_id}"
    #     headers = {"Authorization": f"Bearer {self.access_token}"}
    #     params = {"format": "full"}  # request the full message with all parts

    #     response = requests.get(url, headers=headers, params=params)
    #     if response.status_code != 200:
    #         print("Error fetching email:", response.text)
    #         return {}

    #     msg = response.json()

    #     # Extract sender email, subject and date/time from headers
    #     headers_list = msg["payload"]["headers"]
    #     sender_email = next(
    #         (h["value"] for h in headers_list if h["name"] == "From"), None
    #     )
    #     sent_time = next(
    #         (h["value"] for h in headers_list if h["name"] == "Date"), None
    #     )
    #     subject = next(
    #         (h["value"] for h in headers_list if h["name"] == "Subject"), None
    #     )

    #     # Extract the message text (plain or HTML)
    #     email_body = self.extract_email_text(msg)

    #     return {
    #         "email_address": sender_email,
    #         "subject": subject,
    #         "parsed_text": email_body,
    #         "sent_time": sent_time,  # renamed from 'date_sent'
    #     }

    def extract_email_text(self, msg) -> str:
        """Extracts plain text from Gmail API response (preferring text/plain,
        else fallback to stripping HTML)."""

        payload = msg.get("payload", {})
        # If the email has parts (multipart)
        if "parts" in payload:
            # Check each part for text/plain first
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data")
                if mime_type == "text/plain" and body_data:
                    decoded_text = base64.urlsafe_b64decode(body_data).decode("utf-8")
                    return self.clean_text(decoded_text)

            # If text/plain wasn't found, try text/html
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                body_data = part.get("body", {}).get("data")
                if mime_type == "text/html" and body_data:
                    decoded_html = base64.urlsafe_b64decode(body_data).decode("utf-8")
                    soup = BeautifulSoup(decoded_html, "html.parser")
                    return self.clean_text(soup.get_text())

        else:
            # Single-part emails
            mime_type = payload.get("mimeType", "")
            body_data = payload.get("body", {}).get("data")
            if mime_type == "text/plain" and body_data:
                decoded_text = base64.urlsafe_b64decode(body_data).decode("utf-8")
                return self.clean_text(decoded_text)
            elif mime_type == "text/html" and body_data:
                decoded_html = base64.urlsafe_b64decode(body_data).decode("utf-8")
                soup = BeautifulSoup(decoded_html, "html.parser")
                return self.clean_text(soup.get_text())

        return "No text content found"
