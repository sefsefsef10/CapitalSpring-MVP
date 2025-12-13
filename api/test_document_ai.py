"""Script to generate a test invoice and upload it to test Document AI processing."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import requests
import os
from datetime import datetime

def create_test_invoice(filename: str = "test_invoice.pdf"):
    """Generate a sample invoice PDF."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph("<b>INVOICE</b>", styles['Title']))
    story.append(Spacer(1, 20))

    # Company info
    company_info = """
    <b>Acme Consulting Services LLC</b><br/>
    123 Business Park Drive<br/>
    Suite 400<br/>
    New York, NY 10001<br/>
    Phone: (555) 123-4567<br/>
    Email: billing@acmeconsulting.com
    """
    story.append(Paragraph(company_info, styles['Normal']))
    story.append(Spacer(1, 20))

    # Invoice details
    invoice_details = f"""
    <b>Invoice Number:</b> INV-2024-001234<br/>
    <b>Invoice Date:</b> December 13, 2024<br/>
    <b>Due Date:</b> January 12, 2025<br/>
    <b>Payment Terms:</b> Net 30
    """
    story.append(Paragraph(invoice_details, styles['Normal']))
    story.append(Spacer(1, 20))

    # Bill to
    bill_to = """
    <b>Bill To:</b><br/>
    Capital Spring Fund LP<br/>
    456 Investment Way<br/>
    Greenwich, CT 06830<br/>
    Attention: Accounts Payable
    """
    story.append(Paragraph(bill_to, styles['Normal']))
    story.append(Spacer(1, 30))

    # Line items table
    data = [
        ['Description', 'Quantity', 'Unit Price', 'Amount'],
        ['Consulting Services - Q4 2024', '40 hours', '$250.00', '$10,000.00'],
        ['Due Diligence Review - Project Alpha', '1', '$5,000.00', '$5,000.00'],
        ['Financial Model Development', '1', '$3,500.00', '$3,500.00'],
        ['Travel Expenses (reimbursable)', '1', '$847.50', '$847.50'],
        ['', '', '', ''],
        ['', '', 'Subtotal:', '$19,347.50'],
        ['', '', 'Tax (0%):', '$0.00'],
        ['', '', '<b>Total Due:</b>', '<b>$19,347.50</b>'],
    ]

    table = Table(data, colWidths=[3.5*inch, 1*inch, 1.2*inch, 1.3*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -4), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -4), 1, colors.black),
        ('LINEABOVE', (2, -3), (-1, -3), 1, colors.black),
        ('LINEABOVE', (2, -1), (-1, -1), 2, colors.black),
    ]))
    story.append(table)
    story.append(Spacer(1, 30))

    # Payment info
    payment_info = """
    <b>Payment Information:</b><br/>
    Please make payment to:<br/>
    Bank: First National Bank<br/>
    Account Name: Acme Consulting Services LLC<br/>
    Account Number: 1234567890<br/>
    Routing Number: 021000089<br/>
    Reference: INV-2024-001234
    """
    story.append(Paragraph(payment_info, styles['Normal']))
    story.append(Spacer(1, 20))

    # Footer
    footer = """
    <i>Thank you for your business!</i><br/>
    <small>Payment is due within 30 days of invoice date. Late payments may be subject to a 1.5% monthly finance charge.</small>
    """
    story.append(Paragraph(footer, styles['Normal']))

    doc.build(story)
    print(f"Created test invoice: {filename}")
    return filename


def upload_invoice(filepath: str, api_base: str = "http://127.0.0.1:8000"):
    """Upload the invoice to the API."""
    url = f"{api_base}/api/v1/documents/upload"

    with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f, 'application/pdf')}
        response = requests.post(url, files=files)

    if response.status_code == 200:
        data = response.json()
        print(f"\nUpload successful!")
        print(f"Document ID: {data.get('id')}")
        print(f"Status: {data.get('status')}")
        print(f"GCS Path: {data.get('gcs_path')}")
        return data
    else:
        print(f"\nUpload failed: {response.status_code}")
        print(response.text)
        return None


def check_document_status(doc_id: str, api_base: str = "http://127.0.0.1:8000"):
    """Check the processing status of a document."""
    url = f"{api_base}/api/v1/documents/{doc_id}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"\nDocument Status:")
        print(f"  Status: {data.get('status')}")
        print(f"  Doc Type: {data.get('doc_type')}")
        print(f"  Confidence: {data.get('confidence')}")
        print(f"  Processor: {data.get('processor_used')}")

        if data.get('extracted_data'):
            print(f"\n  Extracted Data:")
            for key, value in data.get('extracted_data', {}).items():
                if not key.startswith('_'):
                    print(f"    {key}: {value}")

        if data.get('processing_error'):
            print(f"\n  Error: {data.get('processing_error')}")

        return data
    else:
        print(f"\nFailed to get document: {response.status_code}")
        print(response.text)
        return None


def reprocess_document(doc_id: str, api_base: str = "http://127.0.0.1:8000"):
    """Trigger reprocessing of a document."""
    url = f"{api_base}/api/v1/documents/{doc_id}/reprocess"
    response = requests.post(url)

    if response.status_code == 200:
        data = response.json()
        print(f"\nReprocess triggered!")
        print(f"  Status: {data.get('status')}")
        return data
    else:
        print(f"\nReprocess failed: {response.status_code}")
        print(response.text)
        return None


if __name__ == "__main__":
    import sys
    import time

    # Create test invoice
    pdf_path = create_test_invoice()

    # Upload it
    result = upload_invoice(pdf_path)

    if result:
        doc_id = result.get('id')

        # Wait a moment for processing
        print("\nWaiting for processing...")
        time.sleep(3)

        # Check status
        check_document_status(doc_id)

        # If it's pending, trigger reprocess
        if result.get('status') == 'pending':
            print("\nTriggering reprocessing...")
            reprocess_document(doc_id)
            time.sleep(3)
            check_document_status(doc_id)
