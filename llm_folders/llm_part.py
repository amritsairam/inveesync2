from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

import os

from pydantic import BaseModel,Field
from llm_folders.parsing import parse_docx,parse_pdf,parse_image,parse_excel


class output(BaseModel):
    final_score: float = Field(description="The score between 0 and 1.00,based on how confident you are on your prediction.")
    classification: str = Field(description="The classification label assigned to the email.")

def classify_email(subject, body,output):
    """
    Classify the content of emails using a language model.

    Args:
        emails: A list of dictionaries containing email subject and body.

    Returns:
        A list of dictionaries containing:
        - "subject": The email's subject.
        - "body": The email body.
        - "classification": The classification label assigned to the email.
    """
    template = '''You are an expert in classifying emails with precision. Your task is to analyze the given email's subject and body and determine if it *contains a purchase order (PO)* or *does not contain a purchase order (PO)*. 

    **Instructions**:
    1. Do not classify the email solely based on the presence of generic terms like "purchase order."
    2. Carefully assess the context and intent of the email's content to make an informed decision.

    **Examples for clarification**:
    - Body: "Please send me the invoice for the purchase order."  
    Classification: This email *does not contain a purchase order* because it is a request for an invoice.

    - Body: "Attaching herewith PO 1234."  
    Classification: This email *contains a purchase order* because it explicitly references an attached PO.

    **Email Content**:
    - Subject: {subject}
    - Body: {body}

    **Question**: Does this email contain a purchase order? Provide a clear classification as either:
    1. *Contains a purchase order*, or  
    2. *Does not contain a purchase order*,  
    along with a brief reasoning for your decision.
    '''


    # Generate a prompt for the language model
    prompt = PromptTemplate(template=template,input_variables=['subject','body'])

    prompt.format(subject=subject,body=body)

    print(prompt)
    llm=ChatOpenAI(model='gpt-4o-2024-11-20',temperature=0)
    llm_with_structure=llm.with_structured_output(output)

    # Use the language model to classify the email
    chain=prompt|llm_with_structure

    output=chain.invoke({'subject':subject,'body':body})

    # classified_emails.append({"subject": subject, "body": body, "classification": classification})

    return output

import os

def identify_file_type(file_path):
    """
    Identifies the file type based on its extension.

    Args:
        file_path (str): The path to the downloaded attachment.

    Returns:
        str: The file type (e.g., 'pdf', 'xlsx', 'jpeg', 'docx') or 'unknown'.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext == '.pdf':
        return 'pdf'
    elif ext in ['.xlsx', '.xls']:
        return 'xlsx'
    elif ext in ['.jpeg', '.jpg','.png']:
        return 'jpeg'
    elif ext == '.docx':
        return 'docx'
    else:
        return 'unknown'
    
def return_corresponding_function(s,path):
    """
    This function takes the file type and the path of the file and returns the parsed string from the file.
    Args:
        s: The file type (e.g., 'pdf', 'xlsx', 'jpeg', 'docx').
        path: The path to the downloaded attachment.
    Returns:
        str: The parsed string from the file.
    """
    if s=="pdf":
        return parse_pdf(path)
    elif s=="xlsx":
        return parse_excel(path)
    elif s=="jpeg":
        return parse_image(path)
    elif s=="docx":
        return parse_docx(path)
    else:
        return "unknown"



if __name__ == '__main__':
    subject = "po attached"
    body = "attached po herewith. we would like it to be shipped as soon as possible"
    # for i in os.listdir('/Users/sairam/Desktop/desktop/inveesync_ai_intern_assigment/test_folder_for_identifying_file_type'):
    #     file_path = os.path.join('/Users/sairam/Desktop/desktop/inveesync_ai_intern_assigment/test_folder_for_identifying_file_type',i)
    #     file_type = identify_file_type(file_path)
    print(classify_email(subject=subject,body=body,output=output).classification)
        # print(f"File type: {file_type}")