from flask import Flask, render_template, request, redirect, url_for
from quickstart import verify_gmail, fetch_emails_with_attachments
from llm_folders.llm_part import classify_email, identify_file_type, return_corresponding_function,output
from llm_folders.parsing import POData, get_schema_string, get_final_structured_output_from_llm
import base64
import os

app = Flask(__name__)


# Initialize the global email data list
email_data_list = []

@app.route('/', methods=['GET'])
def index():
    global email_data_list
    if not email_data_list:
        # Only populate email_data_list if it's empty
        service = verify_gmail()
        emails = fetch_emails_with_attachments(service, label_id="INBOX", max_results=10)
        print(len(emails))
        
        for email in emails:
            email_data = {}
            # print('Email Body:')
            # print(email['body'])
            email_data['subject'] = email.get('subject')
            email_data['body'] = email['body']
            email_data['attachments'] = email.get('attachments')
            email_data['msg_id'] = email.get('msg_id')
            email_data['thread_link'] = f'https://mail.google.com/mail/u/0/#inbox/{email_data["msg_id"]}'
            email_data['contains_po'] = False
            email_data['po_data'] = None

            print('Processing email:', email_data['subject'])

            # Classify email
            classification = classify_email(
                output=output,
                subject=email_data['subject'],
                body=email_data['body']
            ).classification
            print('classification done')

            if classification == "Contains a purchase order":
                email_data['contains_po'] = True
                print('Processing email for purchase order data')

                # Initialize a flag to check if PO data was extracted
                po_data_extracted = False

                # Process attachments if any
                attachments = email.get('attachments', [])
                if attachments:
                    for attachment_path in attachments:
                        file_type = identify_file_type(attachment_path)
                        parsed_string = return_corresponding_function(file_type, attachment_path)
                        schema = get_schema_string(POData)
                        final_output = get_final_structured_output_from_llm(
                            POData,
                            email_data['body'],
                            parsed_string,
                            schema
                        )
                        print('Obtained final output from attachment')
                        email_data['po_data'] = final_output
                        po_data_extracted = True

                        # Encode attachment for display
                        with open(attachment_path, 'rb') as f:
                            encoded_content = base64.b64encode(f.read()).decode('utf-8')
                        attachment_info = {
                            'filename': os.path.basename(attachment_path),
                            'content': encoded_content,
                            'file_type': file_type
                        }
                        email_data['attachments'].append(attachment_info)
                        print('Attachments processed')

                        # Break if you only want to process the first attachment
                        break
                else:
                    print('No attachments found, processing email body')
                    # Since there are no attachments, use the email body
                    schema = get_schema_string(POData)
                    final_output = get_final_structured_output_from_llm(
                        POData,
                        email_data['body'],
                        attachment_string='',
                        schema=schema
                    )
                    print('Obtained final output from email body')
                    email_data['po_data'] = final_output
                    po_data_extracted = True

                if po_data_extracted:
                    print('Purchase order data extracted')
                else:
                    print('Failed to extract purchase order data')
                    email_data['po_data'] = None

            else:
                print('Email does not contain a purchase order')
                email_data['contains_po'] = False
                email_data['po_data'] = None

            email_data_list.append(email_data)

    return render_template('index.html', emails=email_data_list)

@app.route('/update_po/<int:email_index>', methods=['POST'])
def update_po(email_index):
    global email_data_list
    email_data = email_data_list[email_index]

    # Update fields from form data
    po_data = email_data['po_data']
    po_data.customer_po_number = request.form.get('customer_po_number')
    po_data.customer_name = request.form.get('customer_name')

    # # Update customer_details if present
    # if po_data.customer_details:
    #     customer_details = po_data.customer_details
    #     customer_details.phone = request.form.get('customer_details_phone')
    #     customer_details.email = request.form.get('customer_details_email')
    #     customer_details.GST = request.form.get('customer_details_GST')

    # Update items
    items = po_data.items
    for idx, item in enumerate(items):
        item.item_name = request.form.get(f'items-{idx}-item_name')
        item.quantity = int(request.form.get(f'items-{idx}-quantity') or '0')
        item.rate_per_unit = float(request.form.get(f'items-{idx}-rate_per_unit') or '0')
        item.unit_of_measurement = request.form.get(f'items-{idx}-unit_of_measurement')
        item.delivery_date = request.form.get(f'items-{idx}-delivery_date')

    # Update other fields as needed...

    # Redirect back to the index page
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)