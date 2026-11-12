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

def get_keywords():
    doc = prefs_collection.find_one({"_id": "keywords"})
    return doc["words"] if doc else ["student", "intern", "software", "סטודנט"]

def save_keywords(words):
    prefs_collection.update_one({"_id": "keywords"}, {"$set": {"words": words}}, upsert=True)

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    
    if "message" in update and "text" in update["message"]:
        text = update["message"]["text"].strip().lower()
        chat_id = str(update["message"]["chat"]["id"])
        
        # Security: Ensure only the authorized user can execute commands
        if chat_id != CHAT_ID:
            return "Unauthorized", 403

        keywords = set(get_keywords())
        reply_text = ""

        # Process commands
        if text.startswith("/add "):
            word = text.replace("/add ", "").strip()
            keywords.add(word)
            save_keywords(list(keywords))
            reply_text = f"✅ המילה '{word}' הוספה בהצלחה למסד הנתונים."
            
        elif text.startswith("/remove "):
            word = text.replace("/remove ", "").strip()
            if word in keywords:
                keywords.remove(word)
                save_keywords(list(keywords))
                reply_text = f"🗑️ המילה '{word}' הוסרה."
            else:
                reply_text = f"⚠️ המילה '{word}' לא קיימת ברשימה."
                
        elif text == "/help":
            current_words = ", ".join(keywords) if keywords else "אין כרגע"
            reply_text = (
                "🤖 <b>מדריך לבוט JobHunter:</b>\n\n"
                "➕ <code>/add [word]</code> - הוספת מילת מפתח\n"
                "➖ <code>/remove [word]</code> - הסרת מילת מפתח\n"
                "ℹ️ <code>/help</code> - הצגת תפריט זה\n\n"
                f"📝 <b>מילות המפתח שלך:</b> {current_words}"
            )
        
        # Send reply to Telegram
        if reply_text:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"}
            )
            
    return "OK", 200