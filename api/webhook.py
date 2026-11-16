import os
import requests
from flask import Flask, request
from pymongo import MongoClient

app = Flask(__name__)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
MONGO_URI = os.environ.get("MONGO_URI")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.get_database("jobhunter_db")
prefs_collection = db.get_collection("preferences")

def get_preferences():
    """Retrieve job types and field keywords from MongoDB preferences collection."""
    doc = prefs_collection.find_one({"_id": "keywords"})
    if doc:
        job_types = doc.get("job_types", ["student", "intern", "סטודנט"])
        field_keywords = doc.get("field_keywords", ["software", "developer", "backend", "python", "c", "java"])
    else:
        job_types = ["student", "intern", "סטודנט"]
        field_keywords = ["software", "developer", "backend", "python", "c", "java"]
    return set(job_types), set(field_keywords)

def save_preferences(job_types, field_keywords):
    """Save updated job types and field keywords back to MongoDB preferences collection."""
    prefs_collection.update_one(
        {"_id": "keywords"}, 
        {"$set": {
            "job_types": list(job_types),
            "field_keywords": list(field_keywords)
        }}, 
        upsert=True
    )

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram."""
    update = request.get_json()
    
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"].strip()
        text_lower = text.lower()
        chat_id = str(update["message"]["chat"]["id"])
        
        # Security: Ensure only the authorized user can execute commands
        if chat_id != CHAT_ID:
            return "Unauthorized", 403

        job_types, field_keywords = get_preferences()
        reply_text = ""

        # Process commands for separate job types and field keywords
        if text_lower.startswith("/add_type "):
            word = text.split("/add_type ", 1)[1].strip()
            job_types.add(word)
            save_preferences(job_types, field_keywords)
            reply_text = f"✅ התווסף סוג משרה: <b>{word}</b>"
            
        elif text_lower.startswith("/remove_type "):
            word = text.split("/remove_type ", 1)[1].strip()
            if word in job_types:
                job_types.remove(word)
                save_preferences(job_types, field_keywords)
                reply_text = f"🗑 הוסר סוג משרה: <b>{word}</b>"
            else:
                reply_text = f"⚠️ סוג משרה '{word}' לא נמצא ברשימה."
                
        elif text_lower.startswith("/add_field "):
            word = text.split("/add_field ", 1)[1].strip()
            field_keywords.add(word)
            save_preferences(job_types, field_keywords)
            reply_text = f"✅ התווסף תחום טכני: <b>{word}</b>"
            
        elif text_lower.startswith("/remove_field "):
            word = text.split("/remove_field ", 1)[1].strip()
            if word in field_keywords:
                field_keywords.remove(word)
                save_preferences(job_types, field_keywords)
                reply_text = f"🗑 הוסר תחום טכני: <b>{word}</b>"
            else:
                reply_text = f"⚠️ תחום טכני '{word}' לא נמצא ברשימה."
                
        elif text_lower == "/status":
            reply_text = (
                f"📊 <b>סטטוס סינון משרות (MongoDB):</b>\n\n"
                f"<b>סוגי משרה:</b>\n{', '.join(job_types)}\n\n"
                f"<b>תחומים טכניים:</b>\n{', '.join(field_keywords)}"
            )

        elif text_lower == "/help":
            reply_text = (
                f"🤖 <b>פקודות זמינות לניהול JobHunter:</b>\n\n"
                f"• /status - הצגת רשימת מילות המפתח וסוגי המשרות הפעילים\n"
                f"• /add_type [מילה] - הוספת סוג משרה חדש (למשל: /add_type intern)\n"
                f"• /remove_type [מילה] - הסרת סוג משרה\n"
                f"• /add_field [מילה] - הוספת מילת מפתח טכנית (למשל: /add_field c++)\n"
                f"• /remove_field [מילה] - הסרת מילת מפתח טכנית\n"
                f"• /help - הצגת תפריט זה"
            )
        
        # Send reply back to Telegram
        if reply_text:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"}
            )
            
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))