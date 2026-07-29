from src.alerts.email import send_alert
import os

print("Sending test email...")
send_alert(
    article_title="[TEST] Special Situations Radar Email Test",
    article_url="https://github.com",
    event_family="System Test",
    confidence=100,
    research_summary="This is a test email to verify that your SMTP credentials in GitHub Secrets are working correctly. If you received this, your radar is fully operational!"
)
print("Test complete.")
