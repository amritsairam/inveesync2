import os.path
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import re
import base64
from bs4 import BeautifulSoup  # Requires `beautifulsoup4` package
from googleapiclient.errors import HttpError

import re
import base64
import os
from bs4 import BeautifulSoup  # Requires `beautifulsoup4` package
from googleapiclient.errors import HttpError
import logging

from llm_folders.llm_part import output,classify_email,identify_file_type,return_corresponding_function

from llm_folders.parsing import parse_pdf,parse_excel,parse_image,parse_docx
from llm_folders.parsing import POData,POItem,get_schema_string,get_final_structured_output_from_llm

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def verify_gmail():
    """Authenticate and return the Gmail API service instance."""
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
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service

    except HttpError as error:
        print(f"An error occurred: {error}")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_emails_with_attachments(service, label_id="INBOX", max_results=1):
    """
    Fetch emails from the user's Gmail inbox, extract the subject and cleaned body,
    and download any attachments.

    Args:
        service: The Gmail API service object.
        label_id: The label ID to filter emails (default is "INBOX").
        max_results: The maximum number of emails to fetch (default is 5).

    Returns:
        A list of dictionaries containing:
            - "subject": The email's subject.
            - "body": The cleaned email body.
            - "attachments": A list of file paths to downloaded attachments.
            - "msg_id": The message ID of the email.
    """
    try:
        # Ensure the temp folder exists
        temp_folder = "temp"
        os.makedirs(temp_folder, exist_ok=True)

        # Fetch emails from the specified label
        results = service.users().messages().list(
            userId="me", labelIds=[label_id], maxResults=max_results
        ).execute()
        messages = results.get("messages", [])

        emails = []
        for msg in messages:
            msg_id = msg["id"]
            print(f"Processing message ID: {msg_id}")

            # Fetch the full email content
            message = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            # Extract the subject from headers
            headers = message.get("payload", {}).get("headers", [])
            subject = next(
                (header["value"] for header in headers if header["name"] == "Subject"),
                "No Subject"
            )

            # Extract the body
            body = extract_email_body(message)

            # Clean the body
            cleaned_body = clean_email_body(body)

            # Fetch and download attachments
            attachments = download_attachments(service, message, temp_folder)

            # Append to emails list
            emails.append({
                "subject": subject,
                "body": cleaned_body,
                "attachments": attachments,
                "msg_id": msg_id  # Store msg_id here
            })

        return emails

    except HttpError as error:
        logger.error(f"An error occurred while fetching emails: {error}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return []

def extract_email_body(message):
    """
    Extracts the raw body from the email message, including only text/plain parts.

    Args:
        message: The raw email message data.

    Returns:
        A string containing the raw email body.
    """
    body = ""

    def extract_parts(parts):
        nonlocal body
        for part in parts:
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")

            # Skip attachments
            if filename:
                continue

            if mime_type == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    try:
                        decoded_data = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        body += decoded_data + "\n"
                    except Exception as e:
                        logger.warning(f"Failed to decode text/plain part: {e}")
            elif mime_type.startswith("multipart/"):
                # Recursively extract from nested parts
                extract_parts(part.get("parts", []))
            else:
                # Skip other MIME types (e.g., text/html, images)
                continue

    payload = message.get("payload", {})
    mime_type = payload.get("mimeType", "")
    if mime_type.startswith("multipart/"):
        extract_parts(payload.get("parts", []))
    else:
        # Single part message
        part = payload
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                try:
                    decoded_data = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    body += decoded_data + "\n"
                except Exception as e:
                    logger.warning(f"Failed to decode text/plain part: {e}")

    return body.strip()



def clean_email_body(body):
    """
    Cleans the email body text by removing URLs and excessive whitespace.

    Args:
        body: The raw email body as a string.

    Returns:
        A cleaned version of the body.
    """
    # Remove URLs starting with http or https
    body = re.sub(r"http[s]?://\S+", "", body)

    # Remove excessive whitespace
    body = re.sub(r"\s+", " ", body).strip()


    return body


def download_attachments(service, message, temp_folder):
    """
    Identifies and downloads attachments from the email message.

    Args:
        service: The Gmail API service object.
        message: The full email message data.
        temp_folder: Directory to store downloaded attachments.

    Returns:
        A list of file paths to the downloaded attachments.
    """
    attachments = []
    payload = message.get("payload", {})
    parts = payload.get("parts", [])

    if not parts:
        return attachments  # No attachments

    for part in parts:
        filename = part.get("filename")
        if filename:
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            if attachment_id:
                try:
                    attachment = service.users().messages().attachments().get(
                        userId="me", messageId=message["id"], id=attachment_id
                    ).execute()
                    data = attachment.get("data")
                    if data:
                        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                        file_path = os.path.join(temp_folder, filename)
                        with open(file_path, 'wb') as f:
                            f.write(file_data)
                        attachments.append(file_path)
                        logger.info(f"Downloaded attachment: {file_path}")
                except HttpError as error:
                    logger.error(f"An error occurred while downloading attachment {filename}: {error}")
                except Exception as e:
                    logger.error(f"Failed to download attachment {filename}: {e}")
        elif 'parts' in part:
            # Handle nested parts (e.g., multiple attachments in a multipart/mixed email)
            attachments.extend(download_attachments(service, part, temp_folder))

    return attachments



# Example usage
if __name__ == "__main__":
    service = verify_gmail()  # Authenticate and get the Gmail API service object

    # Fetch the latest emails with cleaned body
    emails = fetch_emails_with_attachments(service, label_id="INBOX", max_results=1)

    # Print the subject and cleaned body of each email
    for email in emails:
        subject = email["subject"]
        body = email["body"]
        if email['attachments']:
            attachment_path=email['attachments'][0]
            if classify_email(output=output,subject=email['subject'],body=email['body']).classification=="Contains a purchase order":
                file_type = identify_file_type(attachment_path)
                parsed_string_from_attachment=return_corresponding_function(file_type,attachment_path)
                schema_to_pass_into_prompt=get_schema_string(POData)
                final_output=get_final_structured_output_from_llm(POData,body,parsed_string_from_attachment,schema_to_pass_into_prompt)
                print(type(final_output))
        
