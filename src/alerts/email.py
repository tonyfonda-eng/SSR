"""
SSR 2.0: Downstream Strategy & Execution Engine
Consumes the Canonical Decision Manifest and dispatches targeted email alerts.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config.secrets import GMAIL_USER, GMAIL_APP_PASSWORD

def send_alert(decision_manifest: dict, recipient: str = "tony.fonda@gmail.com"):
    """
    Parses the Canonical Decision Manifest to construct and dispatch an alert email.
    """
    # Defensive check: ensure credentials are loaded
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print(" [WARNING] Email credentials not configured. Skipping alert dispatch.")
        return

    # Extract required fields from the Manifest Structure
    reg = decision_manifest.get("manifest_registry", {})
    det = decision_manifest.get("detection_vector", {})
    prov = decision_manifest.get("evidentiary_provenance_dag", {})
    lineage = decision_manifest.get("syndication_lineage", {})

    event_family = det.get("detected_event_type", "Unknown Event")
    ticker = det.get("target_ticker", "UNKNOWN")
    decision_id = reg.get("decision_id", "Unknown Decision ID")
    sensor = lineage.get("canonical_sensor_id", "Unknown Source")
    timestamp = reg.get("execution_timestamp_gmt", "Unknown Time")

    # The title and URL are not strictly in the manifest structure shown previously, 
    # but practically they'd be passed down. For backward compatibility with the existing
    # code calling signature, we assume they might be added or we use defaults if missing.
    # We'll try to extract them if they are in the manifest, otherwise fallback.
    article_title = decision_manifest.get("headline", f"Event Detected for {ticker}")
    article_url = decision_manifest.get("url", "#")
    research_summary = decision_manifest.get("research_summary", "No summary provided.")
    is_update = decision_manifest.get("is_update", False)

    # Reconstruct Confidence
    conf_decomp = det.get("confidence_decomposition", {})
    agg_conf = conf_decomp.get("aggregate_confidence", 0.0)
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
    
    supporting_evidence = prov.get("supporting_evidence", [])
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
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f" [EMAIL DISPATCH] Alert successfully sent to {recipient} for {ticker}")
    except Exception as e:
        print(f" [EMAIL ERROR] SMTP dispatch failed: {e}")
        raise e