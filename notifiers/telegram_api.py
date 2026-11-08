import os
import requests
from dotenv import load_dotenv
import json

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


PREFS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "preferences.json")

def load_preferences():
    """Loads filtering keywords from preferences.json. Returns defaults if file doesn't exist."""
    if not os.path.exists(PREFS_FILE):
        return {"keywords": ["student", "intern", "software", "סטודנט"]}
    with open(PREFS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_preferences(prefs):
    """Saves the updated keywords to preferences.json"""
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    with open(PREFS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prefs, f, ensure_ascii=False, indent=4)

def process_telegram_commands(bot_token, chat_id):
    """Fetches new messages from Telegram and updates the preferences file."""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    try:
        response = requests.get(url)
        data = response.json()
    except Exception as e:
        print(f"Error fetching telegram updates: {e}")
        return

    if not data.get("ok") or not data.get("result"):
        return

    prefs = load_preferences()
    keywords = set(prefs.get("keywords", []))
    highest_update_id = 0
    preferences_changed = False

    for update in data["result"]:
        update_id = update["update_id"]
        highest_update_id = max(highest_update_id, update_id)
        
        message = update.get("message", {})
        # Only process messages from your specific chat ID for security
        if str(message.get("chat", {}).get("id")) != str(chat_id):
            continue

        text = message.get("text", "").lower().strip()
        
        # Parse commands
        if text.startswith("/add "):
            word = text.replace("/add ", "").strip()
            keywords.add(word)
            preferences_changed = True
        elif text.startswith("/remove "):
            word = text.replace("/remove ", "").strip()
            if word in keywords:
                keywords.remove(word)
                preferences_changed = True
        elif text == "/help":
            # Display current keywords or a default message if the set is empty
            current_words = ", ".join(keywords) if keywords else "אין כרגע"
            help_text = (
                "🤖 <b>מדריך לבוט JobHunter:</b>\n\n"
                "➕ <code>/add [word]</code> - הוספת מילת מפתח (למשל: /add backend)\n"
                "➖ <code>/remove [word]</code> - הסרת מילת מפתח (למשל: /remove student)\n"
                "ℹ️ <code>/help</code> - הצגת תפריט זה\n\n"
                f"📝 <b>מילות המפתח הנוכחיות שלך:</b> {current_words}"
            )
            # Send the help message reply back to Telegram
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": help_text, "parse_mode": "HTML"}
            )
                
    if preferences_changed:
        prefs["keywords"] = list(keywords)
        save_preferences(prefs)
        print(f"Updated preferences via Telegram: {prefs['keywords']}")

    # Acknowledge messages so Telegram removes them from the queue
    if highest_update_id > 0:
        requests.get(f"{url}?offset={highest_update_id + 1}")
    

# Test block - runs only if this file is executed directly
if __name__ == "__main__":
    print("Testing Telegram connection...")
    send_job_alert("משרת פיתוח Backend (בדיקה)", "https://example.com")