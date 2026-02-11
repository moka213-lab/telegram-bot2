import os
import logging
import asyncio
import sqlite3
import csv
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template_string, session, redirect, jsonify, send_file
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================== CONFIG ==================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "ultra-secret")
PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== DATABASE ==================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    joined_at TEXT,
    blocked INTEGER DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS broadcasts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    sent_at TEXT,
    success INTEGER,
    failed INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    created_at TEXT
)""")

conn.commit()

# ================== TELEGRAM ==================
application = Application.builder().token(TOKEN).build()

keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("السنة الأولى")],
     [KeyboardButton("السنة الثانية")],
     [KeyboardButton("السنة الثالثة")],
     [KeyboardButton("السنة الرابعة")]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("INSERT OR IGNORE INTO users(user_id,name,joined_at) VALUES(?,?,?)",
                   (user.id, user.first_name, datetime.now().isoformat()))
    conn.commit()

    await update.message.reply_text("🎓 أهلاً بك في بوت أصول الدين", reply_markup=keyboard)

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📚 سيتم إضافة المحتوى قريباً")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

# ================== FLASK ==================
app = Flask(__name__)
app.secret_key = SECRET_KEY

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return wrap

# ================== WEBHOOK ==================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "OK"

@app.route("/set_webhook")
def set_webhook():
    async def hook():
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    asyncio.run(hook())
    return "Webhook Set"

@app.route("/webhook_status")
@login_required
def webhook_status():
    async def get():
        return await application.bot.get_webhook_info()
    info = asyncio.run(get())
    return jsonify(info.to_dict())

# ================== DASHBOARD ==================
@app.route("/")
def home():
    return "Bot Running"

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
    return "<form method='post'><input type='password' name='password'/><button>Login</button></form>"

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard")
@login_required
def dashboard():
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM broadcasts")
    broadcasts = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(success), SUM(failed) FROM broadcasts")
    stats = cursor.fetchone()
    success = stats[0] or 0
    failed = stats[1] or 0

    return render_template_string("""
    <h1>Ultimate Dashboard</h1>
    <p>Users: {{u}}</p>
    <p>Broadcasts: {{b}}</p>
    <p>Success: {{s}}</p>
    <p>Failed: {{f}}</p>
    <a href='/users'>Users</a><br>
    <a href='/broadcast_page'>Send Broadcast</a><br>
    <a href='/logs'>Logs</a><br>
    <a href='/webhook_status'>Webhook Status</a><br>
    <a href='/export_users'>Export Users CSV</a><br>
    <a href='/logout'>Logout</a>
    """, u=users, b=broadcasts, s=success, f=failed)

# ================== USERS ==================
@app.route("/users")
@login_required
def users():
    cursor.execute("SELECT * FROM users ORDER BY joined_at DESC")
    data = cursor.fetchall()
    return jsonify(data)

@app.route("/delete_user/<int:id>")
@login_required
def delete_user(id):
    cursor.execute("DELETE FROM users WHERE user_id=?", (id,))
    conn.commit()
    return redirect("/dashboard")

@app.route("/export_users")
@login_required
def export_users():
    cursor.execute("SELECT * FROM users")
    data = cursor.fetchall()
    with open("users.csv","w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID","Name","Joined"])
        writer.writerows(data)
    return send_file("users.csv", as_attachment=True)

# ================== BROADCAST ==================
@app.route("/broadcast_page")
@login_required
def broadcast_page():
    return """
    <form method='post' action='/broadcast'>
    <textarea name='message'></textarea><br>
    <button>Send</button>
    </form>
    """

@app.route("/broadcast", methods=["POST"])
@login_required
def broadcast():
    msg = request.form["message"]

    cursor.execute("SELECT user_id FROM users WHERE blocked=0")
    users = cursor.fetchall()

    success = 0
    failed = 0

    async def send():
        nonlocal success, failed
        for u in users:
            try:
                await application.bot.send_message(u[0], msg)
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1

    asyncio.run(send())

    cursor.execute("INSERT INTO broadcasts(message,sent_at,success,failed) VALUES(?,?,?,?)",
                   (msg, datetime.now().strftime("%Y-%m-%d %H:%M"), success, failed))
    conn.commit()

    return redirect("/dashboard")

# ================== LOGS ==================
@app.route("/logs")
@login_required
def logs():
    cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50")
    return jsonify(cursor.fetchall())

# ================== START ==================
if __name__ == "__main__":
    asyncio.run(application.initialize())

    if WEBHOOK_URL:
        async def hook():
            await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        asyncio.run(hook())

    app.run(host="0.0.0.0", port=PORT)
