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
from quickstart import verify_gmail,fetch_emails_with_attachments

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]




# Proceed with processing emails
if __name__ == "__main__":
    service = verify_gmail()  # Authenticate and get the Gmail API service object

    # Fetch the latest emails with cleaned body
    emails = fetch_emails_with_attachments(service, label_id="INBOX", max_results=1)

    # Print the subject and cleaned body of each email
    for email in emails:
        subject = email["subject"]
        body = email["body"]
        if email["attachments"]:
            attachment_path = email["attachments"][0]
            if classify_email(output=output, subject=subject, body=body).classification == "Contains a purchase order":
                if attachment_path:
                    file_type = identify_file_type(attachment_path)
                    parsed_string_from_attachment = return_corresponding_function(file_type, attachment_path)
                    schema_to_pass_into_prompt = get_schema_string(POData)
                    final_output = get_final_structured_output_from_llm(POData, body, parsed_string_from_attachment, schema_to_pass_into_prompt)
                    print(type(final_output))
            else:
                print("Email does not contain a purchase order")
        else:
            print("No attachments found")



    
