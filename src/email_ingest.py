import imaplib
import email
import os
import io
from email.header import decode_header
import PyPDF2
from datetime import datetime
import time

def get_imap_credentials():
    server = os.environ.get("IMAP_SERVER", "imap.gmail.com")
    user = os.environ.get("IMAP_USER")
    password = os.environ.get("IMAP_PASS")
    return server, user, password

def extract_text_from_pdf_bytes(pdf_bytes):
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text += page.extract_text() + "\n"
    except Exception as e:
        print(f"[ERROR] Failed to parse PDF: {e}")
    return text

def connect_imap():
    server, user, password = get_imap_credentials()
    if not user or not password:
        print("[WARNING] IMAP_USER or IMAP_PASS not set. Skipping email ingestion.")
        return None
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, password)
        return mail
    except Exception as e:
        print(f"[ERROR] IMAP connection failed: {e}")
        return None

def fetch_kedm_pdfs(mail):
    """
    Searches for unread emails from KEDM containing PDFs,
    downloads the PDF, extracts text, and marks as read.
    Returns a list of dicts: [{'title': str, 'body': str, 'published': str}]
    """
    mail.select("inbox")
    # Search for UNREAD emails from KEDM
    # You can tune this search query depending on the actual sender or subject
    status, messages = mail.search(None, '(UNREAD FROM "kedm")')
    
    if status != "OK":
        return []

    email_ids = messages[0].split()
    articles = []

    for e_id in email_ids:
        status, msg_data = mail.fetch(e_id, "(RFC822)")
        if status != "OK":
            continue
            
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    try:
                        subject = subject.decode(encoding or "utf-8")
                    except:
                        subject = subject.decode("utf-8", errors="ignore")

                published = msg.get("Date", "")
                
                # Check for attachments
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_maintype() == "multipart":
                            continue
                        if part.get("Content-Disposition") is None:
                            continue
                            
                        filename = part.get_filename()
                        if filename and filename.lower().endswith(".pdf"):
                            print(f"[INGESTION] Downloading PDF attachment: {filename} from '{subject}'")
                            pdf_bytes = part.get_payload(decode=True)
                            body_text = extract_text_from_pdf_bytes(pdf_bytes)
                            
                            articles.append({
                                "id": filename,
                                "title": subject,
                                "url": f"email://{filename}",
                                "published": published,
                                "body": body_text
                            })
                            break # Assume 1 PDF per email is the report
                            
        # Mark as read
        mail.store(e_id, '+FLAGS', '\\Seen')
        
    return articles
