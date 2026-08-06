import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from src.config.secrets import GMAIL_USER, GMAIL_APP_PASSWORD

def send_audit_email(report_filepath: str, recipient: str = "tony.fonda@gmail.com"):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or GMAIL_USER == "your-email@gmail.com":
        print(" [WARNING] Email credentials not configured. Skipping daily audit email.")
        return

    env_recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")
    if env_recipient:
        recipient = env_recipient

    date_str = os.path.basename(report_filepath).replace('.md', '')
    subject = f"SSR Daily Audit — {date_str}"
    
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"SSR Operations <{GMAIL_USER}>"
    msg["To"] = recipient

    body = f"Attached is the Special Situations Radar Daily Forensic Audit report for {date_str}."
    msg.attach(MIMEText(body, "plain"))

    try:
        with open(report_filepath, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(report_filepath)}",
        )
        msg.attach(part)
    except Exception as e:
        print(f" [ERROR] Could not attach report {report_filepath}: {e}")
        return

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f" [EMAIL DISPATCH] Daily audit successfully sent to {recipient}")
    except Exception as e:
        print(f" [EMAIL ERROR] SMTP dispatch failed: {e}")
        raise e

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_audit_email(sys.argv[1])
    else:
        print("Usage: python -m src.notifications.send_report_email <path_to_markdown>")
