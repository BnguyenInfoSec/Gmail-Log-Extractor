# Gmail Filter Project

# Connects to Gmail API using OAuth2, retrieves emails from a specific sender,
# extracts their content, and saves them as text files organized by year and month.
# The script handles pagination to ensure all relevant emails are processed,
# and it cleans filenames to avoid issues with invalid characters.

# If token.json already exists, it reuses saved credentials.
# Otherwise, it initiates OAuth2 flow and stores new credentials.
# Uses BeautifulSoup to extract readable text from HTML emails.


# Standard libraries for file handling, encoding, and date parsing
# Third-party libraries for HTML parsing and Gmail/Drive API interaction

import os
import re
import base64
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# Gmail API permission scope
# gmail.readonly -> read emails only
# drive.file -> create/upload files to Google Drive

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


# CONFIGURATION:
# TARGET_SENDER -> email source
# EMAIL_QUERY -> Gmail search query to filter emails
# OUTPUT_DIR -> local storage
# DRIVE_ROOT_FOLDER_ID -> shared Google Drive destination
# RUN_MODE -> "weekly" or "full"
# WEEKLY_DAYS_BACK -> days to look back in weekly mode

TARGET_SENDER = "example@example.com"

RUN_MODE = "full"  # options: "weekly" or "full"
WEEKLY_DAYS_BACK = 7

if RUN_MODE == "weekly":
    EMAIL_QUERY = f"from:{TARGET_SENDER} newer_than:{WEEKLY_DAYS_BACK}d"
else:
    EMAIL_QUERY = f"from:{TARGET_SENDER}"

OUTPUT_DIR = Path("exported_logs")
DRIVE_ROOT_FOLDER_ID = "Insert Google Drive Folder ID Here"


# Removes invalid filename characters so files can be safely saved
def clean_filename(text):
    text = re.sub(r'[\\/*?:"<>|]', "_", text)
    return text[:120]


# Extracts header values like From, Subject, Date
def get_header(headers, name):
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


# Decodes Gmail's base64url-encoded email content
def decode_part(data):
    if not data:
        return ""
    data = data.replace("-", "+").replace("_", "/")
    return base64.b64decode(data).decode("utf-8", errors="replace")


# Extracts email body
# Prefers plain text, falls back to HTML parsing
def extract_body(payload):
    if "parts" in payload:
        plain_text = ""
        html_text = ""

        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data")

            if mime_type == "text/plain":
                plain_text += decode_part(body_data)

            elif mime_type == "text/html":
                html_text += decode_part(body_data)

            elif "parts" in part:
                plain_text += extract_body(part)

        if plain_text.strip():
            return plain_text.strip()

        if html_text.strip():
            soup = BeautifulSoup(html_text, "html.parser")
            return soup.get_text(separator="\n").strip()

    body_data = payload.get("body", {}).get("data")
    return decode_part(body_data).strip()


# Handles OAuth2 authentication for Gmail + Drive
def get_credentials():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                open_browser=False,
                timeout_seconds=300
            )

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds


# Creates Gmail API service
def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())


# Creates Drive API service
def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


# Finds or creates folder in Google Drive
def find_or_create_drive_folder(drive_service, folder_name, parent_folder_id):
    query = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_folder_id}' in parents "
        f"and trashed = false"
    )

    results = drive_service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    folders = results.get("files", [])

    if folders:
        return folders[0]["id"]

    folder = drive_service.files().create(
        body={
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        },
        fields="id",
        supportsAllDrives=True
    ).execute()

    return folder["id"]


# Checks if a TXT log already exists for a given date (ignores screenshots)
def drive_txt_exists_for_date(drive_service, date_prefix, parent_folder_id):
    query = (
        f"name contains '{date_prefix}' "
        f"and name contains '.txt' "
        f"and '{parent_folder_id}' in parents "
        f"and trashed = false"
    )

    results = drive_service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    return bool(results.get("files", []))


# Uploads file to Drive if a TXT log for that date is not already present
def upload_txt_to_drive(drive_service, local_file_path, filename, parent_folder_id):
    date_prefix = filename[:10]

    if drive_txt_exists_for_date(drive_service, date_prefix, parent_folder_id):
        print(f"Skipped existing Drive TXT log: {filename}")
        return

    drive_service.files().create(
        body={"name": filename, "parents": [parent_folder_id]},
        media_body=MediaFileUpload(local_file_path, mimetype="text/plain"),
        supportsAllDrives=True
    ).execute()

    print(f"Uploaded to Drive: {filename}")


def main():
    print(f"Running in {RUN_MODE.upper()} mode")
    print(f"Gmail query: {EMAIL_QUERY}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Initialize services
    gmail = get_gmail_service()
    drive = get_drive_service()

    # Pagination loop to get ALL matching emails
    messages = []
    next_page_token = None

    while True:
        results = gmail.users().messages().list(
            userId="me",
            q=EMAIL_QUERY,
            maxResults=100,
            pageToken=next_page_token
        ).execute()

        messages.extend(results.get("messages", []))
        next_page_token = results.get("nextPageToken")

        if not next_page_token:
            break

    print(f"Found {len(messages)} matching emails.")

    if not messages:
        return

    # Process each email
    for msg in messages:
        email = gmail.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full"
        ).execute()

        headers = email["payload"]["headers"]

        sender = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date_raw = get_header(headers, "Date")
        normalized_subject = subject.lower().strip()

        if (
            normalized_subject.startswith("re:")
            or normalized_subject.startswith("fwd:")
            or normalized_subject.startswith("fw:")
        ):
            print(f"Skipped reply/forward: {subject}")
            continue

        try:
            email_date = datetime.strptime(date_raw[:25], "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            email_date = datetime.now()

        year = email_date.strftime("%Y")
        month = email_date.strftime("%m-%B")

        folder = OUTPUT_DIR / year / month
        folder.mkdir(parents=True, exist_ok=True)

        body = extract_body(email["payload"])

        filename = clean_filename(
            f"{email_date.strftime('%Y-%m-%d_%H-%M')}_{subject}.txt"
        )

        output_path = folder / filename

        content = f"""From: {sender}
Subject: {subject}
Date: {date_raw}
Gmail Message ID: {msg["id"]}

{"=" * 80}

{body}
"""

        output_path.write_text(content, encoding="utf-8")
        print(f"Saved locally: {output_path}")

        # Drive sync
        year_id = find_or_create_drive_folder(drive, year, DRIVE_ROOT_FOLDER_ID)
        month_id = find_or_create_drive_folder(drive, month, year_id)

        date_prefix = email_date.strftime("%Y-%m-%d")

        if drive_txt_exists_for_date(drive, date_prefix, month_id):
            print(f"Skipped existing TXT log: {date_prefix}")
        else:
            upload_txt_to_drive(drive, output_path, filename, month_id)


if __name__ == "__main__":
    main()
