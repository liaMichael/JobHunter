import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_simple_message(text):
    """A helper function to send standard text messages (for command confirmations)"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.exceptions.RequestException:
        pass

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

def process_telegram_commands(db):
    """
    Checks for recent commands sent to the bot, updates MongoDB preferences, 
    and saves the offset so commands aren't processed twice.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID or db is None:
        return
        
    prefs_col = db["preferences"]
    
    # Retrieve the last processed update_id to avoid repeating commands
    state_doc = prefs_col.find_one({"_id": "telegram_state"})
    offset = state_doc.get("last_update_id", 0) + 1 if state_doc else None

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 5, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
        
    try:
        resp = requests.get(url, params=params).json()
    except Exception as e:
        print(f"Failed to fetch Telegram updates: {e}")
        return
        
    if not resp.get("ok") or not resp.get("result"):
        return
        
    updates = resp["result"]
    highest_update_id = 0
    
    # Load current keywords from DB to manipulate them
    keywords_doc = prefs_col.find_one({"_id": "keywords"}) or {}
    job_types = set(keywords_doc.get("job_types", ["student", "intern", "סטודנט"]))
    field_keywords = set(keywords_doc.get("field_keywords", ["software", "developer", "backend", "python", "c", "java"]))
    
    changes_made = False
    
    for update in updates:
        update_id = update["update_id"]
        if update_id > highest_update_id:
            highest_update_id = update_id
            
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        
        # SECURITY: Only accept commands from your specific Chat ID
        if chat_id != str(CHAT_ID):
            continue
            
        # Parse commands
        if text.startswith("/add_type "):
            word = text.split("/add_type ", 1)[1].strip()
            job_types.add(word)
            changes_made = True
            send_simple_message(f"✅ התווסף סוג משרה: <b>{word}</b>")
            
        elif text.startswith("/remove_type "):
            word = text.split("/remove_type ", 1)[1].strip()
            if word in job_types:
                job_types.remove(word)
                changes_made = True
                send_simple_message(f"🗑 הוסר סוג משרה: <b>{word}</b>")
                
        elif text.startswith("/add_field "):
            word = text.split("/add_field ", 1)[1].strip()
            field_keywords.add(word)
            changes_made = True
            send_simple_message(f"✅ התווסף תחום טכני: <b>{word}</b>")
            
        elif text.startswith("/remove_field "):
            word = text.split("/remove_field ", 1)[1].strip()
            if word in field_keywords:
                field_keywords.remove(word)
                changes_made = True
                send_simple_message(f"🗑 הוסר תחום טכני: <b>{word}</b>")
                
        elif text == "/status":
            status_msg = f"📊 <b>סטטוס סינון משרות (MongoDB):</b>\n\n"
            status_msg += f"<b>סוגי משרה:</b>\n{', '.join(job_types)}\n\n"
            status_msg += f"<b>תחומים טכניים:</b>\n{', '.join(field_keywords)}"
            send_simple_message(status_msg)

    # Save modifications back to MongoDB
    if changes_made:
        prefs_col.update_one(
            {"_id": "keywords"},
            {"$set": {
                "job_types": list(job_types), 
                "field_keywords": list(field_keywords)
            }},
            upsert=True
        )
        print("MongoDB keywords updated via Telegram.")
        
    # Commit the offset so we don't read these messages again
    if highest_update_id > 0:
        prefs_col.update_one(
            {"_id": "telegram_state"},
            {"$set": {"last_update_id": highest_update_id}},
            upsert=True
        )

# Test block
if __name__ == "__main__":
    print("Testing Telegram connection...")
    send_job_alert("משרת פיתוח Backend (בדיקה)", "https://example.com")