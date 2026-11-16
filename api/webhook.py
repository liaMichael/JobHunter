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
            reply_text = f"✅ סוג משרה <b>'{word}'</b> התווסף בהצלחה."
            
        elif text_lower.startswith("/remove_type "):
            word = text.split("/remove_type ", 1)[1].strip()
            if word in job_types:
                job_types.remove(word)
                save_preferences(job_types, field_keywords)
                reply_text = f"🗑️ סוג משרה <b>'{word}'</b> הוסר."
            else:
                reply_text = f"⚠️ סוג משרה <b>'{word}'</b> לא קיים ברשימה."
                
        elif text_lower.startswith("/add_field "):
            word = text.split("/add_field ", 1)[1].strip()
            field_keywords.add(word)
            save_preferences(job_types, field_keywords)
            reply_text = f"✅ התחום הטכני <b>'{word}'</b> התווסף בהצלחה."
            
        elif text_lower.startswith("/remove_field "):
            word = text.split("/remove_field ", 1)[1].strip()
            if word in field_keywords:
                field_keywords.remove(word)
                save_preferences(job_types, field_keywords)
                reply_text = f"🗑️ התחום הטכני <b>'{word}'</b> הוסר."
            else:
                reply_text = f"⚠️ התחום הטכני <b>'{word}'</b> לא קיים ברשימה."
                
        elif text_lower == "/status":
            types_str = ", ".join(job_types) if job_types else "אין כרגע"
            fields_str = ", ".join(field_keywords) if field_keywords else "אין כרגע"
            reply_text = (
                f"📊 <b>סטטוס סינון משרות:</b>\n\n"
                f"🎯 <b>סוגי משרה:</b> {types_str}\n"
                f"💻 <b>תחומים טכניים:</b> {fields_str}"
            )

        elif text_lower == "/help":
            types_str = ", ".join(job_types) if job_types else "אין כרגע"
            fields_str = ", ".join(field_keywords) if field_keywords else "אין כרגע"
            reply_text = (
                "🤖 <b>מדריך לבוט JobHunter:</b>\n\n"
                "➕ <code>/add_type [word]</code> - הוספת סוג משרה\n"
                "➖ <code>/remove_type [word]</code> - הסרת סוג משרה\n"
                "➕ <code>/add_field [word]</code> - הוספת תחום טכני\n"
                "➖ <code>/remove_field [word]</code> - הסרת תחום טכני\n"
                "📊 <code>/status</code> - הצגת הסטטוס המלא\n"
                "ℹ️ <code>/help</code> - הצגת תפריט זה\n\n"
                f"🎯 <b>סוגי משרה פעילים:</b> {types_str}\n"
                f"💻 <b>תחומים טכניים פעילים:</b> {fields_str}"
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