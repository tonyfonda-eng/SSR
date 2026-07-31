import sqlite3
import re
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

from src.issuer import extract_issuing_company

def get_db_connection():
    # Absolute path logic to run from anywhere
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ssr_cache.sqlite")
    return sqlite3.connect(db_path)

def audit_ssd_coverage():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all SSD articles processed in the last 48 hours
    forty_eight_hours_ago = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    
    c.execute('''
        SELECT * FROM articles 
        WHERE source LIKE '%Special Situations Digest%' 
        AND processed_at >= ?
    ''', (forty_eight_hours_ago,))
    
    ssd_articles = c.fetchall()
    
    misses = []
    catches = []
    
    for ssd in ssd_articles:
        ssd_title = ssd['title']
        ssd_body = ssd['body']
        
        # Use the exact same deterministic/AI extraction used in monitor.py for deduplication
        company_name = extract_issuing_company("Special Situations Digest", ssd_title, ssd_body)
        
        if not company_name or company_name == "UNKNOWN":
            continue # Could not parse
            
        # Check if any OTHER source caught this company around the same time
        c.execute('''
            SELECT * FROM articles
            WHERE source NOT LIKE '%Special Situations Digest%'
            AND LOWER(title) LIKE ?
            AND processed_at >= ?
        ''', (f'%{company_name}%', forty_eight_hours_ago))
        
        matches = c.fetchall()
        if matches:
            catches.append((ssd_title, matches[0]['source'], matches[0]['title']))
        else:
            misses.append(ssd_title)
            
    conn.close()
    return catches, misses

def send_audit_report(catches, misses):
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", 587)
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")
    
    subject = f"📊 SSR Audit Report: {len(misses)} Misses, {len(catches)} Catches"
    
    body = "=== SSD COVERAGE AUDIT ===\n\n"
    
    if misses:
        body += f"❌ Misses ({len(misses)}):\n"
        for m in misses:
            body += f"  - MISSED: {m}\n"
        body += "\n"
        
    if catches:
        body += f"✅ Catches ({len(catches)}):\n"
        for c in catches:
            body += f"  - SSD: {c[0]}\n    Caught by: {c[1]} ({c[2]})\n\n"
            
    if not misses and not catches:
        body += "No Special Situations Digest alerts found in the database over the last 48 hours."
    elif not misses:
        body += "Perfect coverage! No misses found in the last 48 hours."
        
    print(body)
    
    if not all([smtp_server, smtp_user, smtp_pass, recipient]):
        print("[INFO] SMTP credentials missing. Email not sent locally.")
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
        print(f"[AUDIT] Report emailed to {recipient}")
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to send email: {e}")

if __name__ == "__main__":
    print("Running SSD Auditor...")
    catches, misses = audit_ssd_coverage()
    send_audit_report(catches, misses)
