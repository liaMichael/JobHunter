import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_job_alert(job_title, job_url, company_name=""):
    """
    Sends a Telegram alert for a new job opening.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Error: Missing Telegram credentials (TELEGRAM_TOKEN or CHAT_ID).")
        return

    # Format the message with basic HTML for readability (User-facing text)
    message_text = f"🚀 <b>משרה חדשה נפתחה!</b>\n\n"
    if company_name:
        message_text += f"🏢 <b>חברה:</b> {company_name}\n"
    message_text += f"💼 <b>תפקיד:</b> {job_title}\n"
    message_text += f"🔗 <a href='{job_url}'>למעבר לעמוד המשרה</a>"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True  # Prevents large link previews
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"Alert sent successfully for: {job_title}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram alert: {e}")

# Test block - runs only if this file is executed directly
if __name__ == "__main__":
    print("Testing Telegram connection...")
    send_job_alert("משרת פיתוח Backend (בדיקה)", "https://example.com")