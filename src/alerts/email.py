"""
SSR 2.0: Downstream Strategy & Execution Engine
Consumes the Canonical Decision Manifest and dispatches targeted email alerts.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config.secrets import GMAIL_USER, GMAIL_APP_PASSWORD

def send_alert(decision_manifest: dict, recipient: str = None):
    """
    Parses the Canonical Decision Manifest to construct and dispatch an alert email.
    """
    # AUDIT FIX 2.4 & 15: Defensive check properly guards against literal placeholder defaults
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or GMAIL_USER == "your-email@gmail.com":
        print(" [WARNING] Email credentials not configured. Skipping alert dispatch.")
        return

    import os
    if not recipient:
        env_recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")
        recipient = env_recipient if env_recipient else GMAIL_USER

    # Extract required fields from the flat Manifest Structure
    event_family = decision_manifest.get("event_type", "Unknown Event")
    ticker = decision_manifest.get("target_ticker", "UNKNOWN")
    decision_id = decision_manifest.get("decision_id", "Unknown Decision ID")
    sensor = decision_manifest.get("canonical_sensor_id", decision_manifest.get("source", "Unknown Source"))
    timestamp = decision_manifest.get("runtime_timestamp", "Unknown Time")

    article_title = decision_manifest.get("headline", f"Event Detected for {ticker}")
    article_url = decision_manifest.get("url", "#")
    research_summary = decision_manifest.get("research_summary", "No summary provided.")
    is_update = decision_manifest.get("is_update", False)

    # Reconstruct Confidence
    ai_core = decision_manifest.get("ai_core_inference", {})
    agg_conf = ai_core.get("aggregate_confidence", 0.0)
    confidence_pct = f"{agg_conf * 100:.1f}%" if agg_conf > 0 else "N/A"

    subject_prefix = "[UPDATE]" if is_update else "[ALERT]"
    subject = f"SSR {subject_prefix} {ticker} - {event_family}"

    # Build the HTML Email Body
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: #333; line-height: 1.5; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 5px; }}
            h2 {{ color: #2ea043; border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }}
            .meta-data {{ background: #f6f8fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }}
            .meta-data strong {{ color: #24292e; display: inline-block; width: 120px; }}
            .research-memo {{ white-space: pre-wrap; background: #fff; padding: 15px; border-left: 4px solid #4088db; font-family: monospace; font-size: 13px; }}
            .evidence {{ margin-top: 20px; font-size: 0.85em; color: #586069; }}
            .footer {{ margin-top: 30px; font-size: 0.8em; color: #6a737d; text-align: center; border-top: 1px solid #eaeaea; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>SSR Strategy Alert: {event_family}</h2>
            
            <div class="meta-data">
                <div><strong>Target Ticker:</strong> {ticker}</div>
                <div><strong>Confidence:</strong> {confidence_pct}</div>
                <div><strong>Sensor Source:</strong> {sensor}</div>
                <div><strong>Timestamp:</strong> {timestamp}</div>
                <div style="margin-top: 10px;"><strong>Source Headline:</strong> <a href="{article_url}">{article_title}</a></div>
            </div>

            <h3>Investment Memo (AI Synthesis)</h3>
            <div class="research-memo">{research_summary}</div>
            
            <h3>Supporting Causal Evidence</h3>
            <ul class="evidence">
    """
    
    supporting_evidence = decision_manifest.get("evidence", [])
    if supporting_evidence:
        for ev in supporting_evidence:
            html_body += f"<li>[{ev.get('component', 'System')}] {ev.get('assertion', 'Matched context')} (Wt: {ev.get('weight', 1.0)})</li>"
    else:
        html_body += "<li>No supporting evidence graph provided.</li>"

    html_body += f"""
            </ul>
            
            <div class="footer">
                Special Situations Radar (SSR 2.0) | Decision ID: {decision_id}<br>
                Manifest Configuration: {reg.get("configuration_manifest_hash", "Unknown")}
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SSR Operations <{GMAIL_USER}>"
    msg["To"] = recipient

    msg.attach(MIMEText(html_body, "html"))

    try:
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f" [EMAIL DISPATCH] Alert successfully sent to {recipient} for {ticker}")
    except Exception as e:
        print(f" [EMAIL ERROR] SMTP dispatch failed: {e}")
        raise e

def send_v4_event_report(event_data: dict, recipient: str = None):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or GMAIL_USER == "your-email@gmail.com":
        print(" [WARNING] Email credentials not configured. Skipping event report.")
        return

    import os
    if not recipient:
        env_recipient = os.environ.get("ALERT_EMAIL_RECIPIENT")
        recipient = env_recipient if env_recipient else GMAIL_USER
        
    event_id = event_data.get("event_id", "UNKNOWN")
    event_type = str(event_data.get("event_type", "Corporate Announcement")).upper()
    hypotheses = event_data.get("hypotheses", [])
    
    subject = f"SSR EVENT: {event_type} - {len(hypotheses)} Strategies Generated"
    
    trades_html = ""
    for t in hypotheses:
        trades_html += f"<li><strong>{t['strategy']}</strong> ({t['ticker']}) - Status: {t['status']}<br>Reason: {t['reason']}</li>"
        
    timeline_html = ""
    history = event_data.get("confidence_history", [])
    for c in history:
        timeline_html += f"<li>Version {c.get('version', '?')} ({c.get('timestamp', 'Unknown')}) - Score: {c.get('score', 0)}<br>Reason: {c.get('reason', 'Unknown')}</li>"
        
    evidence_html = ""
    for e in event_data.get("evidence", []):
        evidence_html += f"<li>{e}</li>"
        
    opportunity_score = event_data.get("opportunity_score", {})
    trend = ""
    if len(history) > 1:
        diff = history[-1].get("score", 0) - history[-2].get("score", 0)
        trend = f" (↑ +{diff})" if diff > 0 else f" (↓ {diff})" if diff < 0 else " (-)"
        
    raw = opportunity_score.get("raw_components", {})
    confidence_html = f"Total: {opportunity_score.get('total', 0)}{trend} (Entity: {raw.get('entity', 0)}, Event: {raw.get('event', 0)}, Trade: {raw.get('trade', 0)}, Financial: {raw.get('financial', 0)})"
        
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; color: #333; line-height: 1.5; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 5px; }}
            h2 {{ color: #2ea043; border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }}
            .meta-data {{ background: #f6f8fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Institutional Event Report: {event_type}</h2>
            
            <div class="meta-data">
                <div><strong>Event ID:</strong> {event_id}</div>
                <div><strong>Event Summary:</strong> {event_type} involving {len(event_data.get('entities', []))} entities.</div>
                <div><strong>Confidence:</strong> {confidence_html}</div>
            </div>

            <h3>Timeline</h3>
            <ul>{timeline_html}</ul>
            
            <h3>Supporting Evidence</h3>
            <ul>{evidence_html}</ul>

            <h3>Tradable Hypotheses</h3>
            <ul>{trades_html}</ul>
            
            <h3>Key Risks</h3>
            <ul><li>Subject to regulatory approval and financing conditions.</li></ul>
            
            <div class="footer">
                Special Situations Radar | V4 Execution Engine
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SSR Operations <{GMAIL_USER}>"
    msg["To"] = recipient

    msg.attach(MIMEText(html_body, "html"))

    try:
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f" [EMAIL DISPATCH] Event Report sent to {recipient}")
    except Exception as e:
        print(f" [EMAIL ERROR] SMTP dispatch failed: {e}")