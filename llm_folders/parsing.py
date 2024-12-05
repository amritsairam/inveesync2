import pandas as pd
import pytesseract
from PIL import Image
import docx
import pdfplumber
from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
import os
from langchain_openai import ChatOpenAI


def parse_excel(file_path):
    """
    Extracts data from an Excel file and returns it as a concatenated string.
    
    Args:
        file_path (str): Path to the Excel file.
        
    Returns:
        str: Concatenated text from all sheets in the Excel file.
    """
    try:
        xls = pd.ExcelFile(file_path)
        extracted_text = ""
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name)
            extracted_text += f"Sheet: {sheet_name}\n"
            extracted_text += df.to_string(index=False)
            extracted_text += "\n\n"
        return extracted_text
    except Exception as e:
        print(f"Error reading Excel file {file_path}: {e}")
        return ""

def parse_docx(file_path):
    """
    Extracts text from a DOCX file and returns it as a single string.
    
    Args:
        file_path (str): Path to the DOCX file.
        
    Returns:
        str: Extracted text from the Word document.
    """
    try:
        doc = docx.Document(file_path)
        extracted_text = "\n".join([para.text for para in doc.paragraphs])
        return extracted_text
    except Exception as e:
        print(f"Error reading DOCX file {file_path}: {e}")
        return ""

def parse_pdf(file_path):
    """
    Extracts text from a PDF file and returns it as a single string.
    
    Args:
        file_path (str): Path to the PDF file.
        
    Returns:
        str: Extracted text from the PDF.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            extracted_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
        return extracted_text
    except Exception as e:
        print(f"Error reading PDF file {file_path}: {e}")
        return ""

def parse_image(file_path):
    """
    Extracts text from an image file using OCR and returns it as a string.
    
    Args:
        file_path (str): Path to the image file.
        
    Returns:
        str: Extracted text from the image.
    """
    try:
        with Image.open(file_path) as img:
            img = img.convert('L')  # Convert to grayscale for better OCR accuracy
            text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Error reading image file {file_path}: {e}")
        return ""
    
image_path='/Users/sairam/Desktop/desktop/inveesync_ai_intern_assigment/test_folder_for_identifying_file_type/test_for_identifying_type.png'


class POItem(BaseModel):
    item_name: str = Field(..., description="Item Name (mandatory)")
    quantity: int = Field(..., description="Quantity (mandatory)")
    rate_per_unit: float = Field(..., description="Rate per unit (mandatory)")
    unit_of_measurement: str = Field(..., description="Unit of measurement (mandatory)")
    delivery_date: str = Field(..., description="Item-wise Delivery Dates (mandatory)")

class POData(BaseModel):
    customer_po_number: str = Field(..., description="Customer PO Number (mandatory)")
    customer_name: str = Field(..., description="Customer Name (mandatory)")
    items: List[POItem] = Field(..., description="List of items (mandatory)")
    customer_details: Optional[str] = Field(None, description="Customer details (Optional)")
    gst_number: Optional[str] = Field(None, description="GST Number (Optional)")
    terms_of_payment: Optional[str] = Field(None, description="Terms of Payment (Optional)")
    discount: Optional[float] = Field(None, description="Discount (Optional)")
    other_remarks: Optional[str] = Field(None, description="Other remarks/instructions (Optional)")

def get_schema_string(pydantic_object):
    """
    Get the schema string for a Pydantic object.
    
    Args:
        pydantic_object: A Pydantic model object.
        
    Returns:
        str: The schema string for the Pydantic object.
    """
    po_data_parser = PydanticOutputParser(pydantic_object=pydantic_object)
    schema_str = po_data_parser.get_format_instructions()
    return schema_str


def get_final_structured_output_from_llm(pydantic_class,body,attachment_string,schema):
    """
    Get the final structured output from the LLM (Language Model) based on the provided information.
    
    Args:
        pydantic_class: The Pydantic model class to use for parsing.
        body: The body of the email.
        attachment_string: The string content of the attachment.
        schema: The schema string for the Pydantic object.
        
    Returns:
        The structured output from the LLM.
    """
    template = '''
    You are an expert at extracting structured data from the provided information.

    **Your Task**:
    Analyze the email body and attachment data to extract the required fields.

    **Required Fields**:
    - Customer PO Number (mandatory)
    - Customer Name (mandatory)
    - Items (mandatory): A list of items, each containing:
    - Item Name (mandatory)
    - Quantity (mandatory)
    - Rate per unit (mandatory)
    - Unit of measurement (mandatory)
    - Delivery date (mandatory)
   - Customer details (Optional): Phone number 
    - gst_number (Optional) :GST number
    - Terms of Payment (Optional)
    - Discount (Optional)
    - Other remarks/instructions (Optional)

    **Instructions**:
    - Provide the extracted information in **JSON format** matching the schema below.
    - If a **mandatory field** is missing, set its value to `"Not found"`.
    - For **optional fields**, you can omit them or set them to `null`.
    - Ensure all data types are correct (e.g., numbers for quantities and rates).
    - Do not include any additional text or explanation in your response; only provide the JSON-formatted data.
    - If the attachment data is empty or not provided, focus on extracting information from the email body.

    **Schema**:
    {schema}

    ### Email Body:
    {body}

    ### Attachment Data:
    {attachment_string}
    '''

    # llm=ChatGroq(model='llama3-groq-8b-8192-tool-use-preview',temperature=0)
    llm=ChatOpenAI(model='gpt-4o-2024-11-20',temperature=0)
    llm_with_structure=llm.with_structured_output(pydantic_class)
    prompt = PromptTemplate(template=template,input_variables=['body','attachment_string','schema'])
    prompt_with_inputs=prompt.format(body=body,attachment_string=attachment_string,schema=schema)
    print(prompt_with_inputs)
    chain=prompt|llm_with_structure
    output=chain.invoke({'body':body,'attachment_string':attachment_string,'schema':schema})
    return output
    
if __name__ == '__main__':
    image_text=parse_image(image_path)
    body='''Dear Sirs, Kindly arrange to supply the below items urgently. Order No.DateItem CodeDescriptionQuantity CO-01075 23/May/2024 410543 0100360135 TERMINAL SCREW 41000.00 CO-01149 27/May/2024 432043 0100360135 TERMINAL SCREW 25000.00 CO-01414 08/Jun/2024 444043 0000360135 FIXED CONTACT SCREW ASSEMBLY 100000.00 CO-01462 11/Jun/2024 433243 0100360135 TERMINAL SCREW 50000.00 CO-01478 12/Jun/2024 432043 0100360135 TERMINAL SCREW 25000.00 Regards, Chi***** M.S SALZER'''
    schema_string=get_schema_string(POData)
    output=get_final_structured_output_from_llm(POData,body,image_text,schema_string)
    print(output)
    # print(image_text)

