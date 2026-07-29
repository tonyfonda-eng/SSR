import os
import smtplib
from email.message import EmailMessage

def send_alert(article_title, article_url, event_family, confidence, research_summary):
    """
    Sends an email alert for a high-confidence cash event.
    If SMTP credentials are not found in the environment, it mocks the email in the console.
    """
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", 587)
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")

    subject = f"🚨 SSR Alert: {event_family} Detected ({article_title})"
    
    body = f"""
Special Situations Radar - Alert

Event: {event_family}
Confidence: {confidence}
Source: {article_title}
URL: {article_url}

=== AI Research Summary ===
{research_summary}
===========================
"""

    if not all([smtp_server, smtp_user, smtp_pass, recipient]):
        print("\n" + "*" * 60)
        print("[MOCK EMAIL ALERT]")
        print(f"Subject: {subject}")
        print(body)
        print("*" * 60 + "\n")
        print("[INFO] SMTP credentials not fully configured. Email printed to console instead.")
        return

    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = recipient

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"[ALERTS] Email sent successfully to {recipient}")
    except Exception as e:
        print(f"[ALERTS] Failed to send email: {e}")
