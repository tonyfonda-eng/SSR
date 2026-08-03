import os
import smtplib
import logging
import datetime
from email.message import EmailMessage

logger = logging.getLogger(__name__)

def send_alert(article_title, article_url, event_family, confidence, research_summary, evidence_log=None, is_update=False):
    """
    Sends an armored email alert for high-confidence special situations cash events.
    Secured against encoding errors, network hangs, and unclosed sockets.
    """
    if evidence_log is None:
        evidence_log = []
        
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")

    # Fixed broken character strings with clean unicode emojis
    if is_update:
        subject = f"🔄 SSR UPDATE: {event_family} Detected ({article_title})"
    else:
        subject = f"🚨 SSR Alert: {event_family} Detected ({article_title})"
    
    evidence_bullets = "\n".join([f"✓ {e}" for e in evidence_log]) if evidence_log else "None recorded."
    
    section_3 = f"""
3. Why did SSR trigger?

Matched Rules:
{evidence_bullets}

System Metric Confidence Score:
{confidence}
"""
    
    # RESILIENT PARSING PASS: Handle varying layout structural text formats dynamically
    target_markers = ["4. Investment Facts", "4. Investment", "4. ", "Investment Facts"]
    full_memo = None
    
    for marker in target_markers:
        if marker in research_summary:
            full_memo = research_summary.replace(marker, f"{section_3}\n{marker}")
            break
            
    if full_memo is None:
        # Secure fallback if markdown headers differ from the expected template
        full_memo = f"{research_summary}\n\n{section_3}"

    body = f"""
Source: {article_title}
URL: {article_url}
Timestamp Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S GMT')}

======================================================================
EXECUTIVE MEMO DETAIL
======================================================================
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
        # Explicitly declare utf-8 content packaging to handle diverse financial text formatting safely
        msg.set_content(body, charset='utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = recipient

        # Armored Network Connection: Injects strict 10s socket connect timeout
        print(f"[ALERTS] Initiating network connection to SMTP server {smtp_server}:{smtp_port}...")
        
        # Context manager pattern guarantees socket death even if transport layers crash mid-run
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10.0) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        print(f"[ALERTS] Email sent successfully to {recipient}")
        
    except smtplib.SMTPTimeoutError:
        error_msg = f"Network timed out connecting to mail transfer agent host: {smtp_server}."
        print(f"[CRITICAL ALERT ERROR] {error_msg}")
        try:
            from src.database import save_exception_log
            save_exception_log(error=error_msg)
        except Exception:
            pass
            
    except Exception as e:
        error_msg = f"MTA Transport layer failed to dispatch pipeline alert message: {e}"
        print(f"[ERROR] {error_msg}")
        try:
            from src.database import save_exception_log
            save_exception_log(error=error_msg)
        except Exception:
            pass