import os
import smtplib
from email.message import EmailMessage

def send_alert(article_title, article_url, event_family, confidence, research_summary, evidence_log=None):
    """
    Sends an email alert for a high-confidence cash event.
    If SMTP credentials are not found in the environment, it mocks the email in the console.
    """
    if evidence_log is None:
        evidence_log = []
        
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", 587)
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")

    subject = f"🚨 SSR Alert: {event_family} Detected ({article_title})"
    
    evidence_bullets = "\n".join([f"✓ {e}" for e in evidence_log]) if evidence_log else "None recorded."
    
    section_3 = f"""
3. Why did SSR trigger?

Matched Rules
{evidence_bullets}

Score
{confidence}
"""
    
    # Inject Section 3 right before Section 4 in the AI's markdown response
    if "4. Investment Facts" in research_summary:
        full_memo = research_summary.replace("4. Investment Facts", f"{section_3}\n4. Investment Facts")
    elif "4. " in research_summary:
        full_memo = research_summary.replace("4. ", f"{section_3}\n4. ")
    else:
        # Fallback if AI messes up the formatting
        full_memo = f"{research_summary}\n\n{section_3}"

    body = f"""
Source: {article_title}
URL: {article_url}

{full_memo}
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
