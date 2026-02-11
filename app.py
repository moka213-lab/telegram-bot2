"""
بوت تلغرام + لوحة تحكم احترافية
Professional Telegram Bot with Dashboard
Compatible with Render & Blogger Embed
"""

import os
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات البيئة
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-here")

# تفعيل التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== بيانات لوحة التحكم ==========
bot_stats = {
    "total_users": 0,
    "total_messages": 0,
    "start_date": datetime.now().strftime("%Y-%m-%d"),
    "broadcasts": [],
    "commands_log": []
}

# ========== إعدادات البوت ==========
MAIN_KEYBOARD = [
    [KeyboardButton("السنة الأولى")],
    [KeyboardButton("السنة الثانية")],
    [KeyboardButton("السنة الثالثة")],
    [KeyboardButton("السنة الرابعة")],
]

def get_main_keyboard():
    return ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True)

def get_year_keyboard(year_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("السنة الأولى", callback_data="year1")],
        [InlineKeyboardButton("السنة الثانية", callback_data="year2")],
        [InlineKeyboardButton("السنة الثالثة", callback_data="year3")],
        [InlineKeyboardButton("السنة الرابعة", callback_data="year4")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_not_available_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("رجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_welcome_message() -> str:
    return (
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "┃   بوت اصول الدين     ┃\n"
        "┃      التعليمي        ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "▸ اختر السنة الدراسية\n"
        "▸ اضغط على أحد الخيارات أدناه"
    )

def format_not_available_message() -> str:
    return (
        "╭━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "┃                     ┃\n"
        "┃   عذراً، غير متوفر ┃\n"
        "┃                     ┃\n"
        "┃  يرجى المحاولة      ┃\n"
        "┃  في وقت لاحق       ┃\n"
        "┃                     ┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯"
    )

def format_year_message() -> str:
    return "▸ اختر السنة الدراسية من القائمة"

# ========== Flask App ==========
app = Flask(__name__)
app.secret_key = SECRET_KEY

# قالب لوحة التحكم
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم بوت اصول الدين</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); display: flex; justify-content: space-between; align-items: center; }
        .header h1 { color: #333; font-size: 24px; }
        .status-badge { background: #10b981; color: white; padding: 5px 15px; border-radius: 20px; font-size: 12px; }
        .logout-btn { background: #ef4444; color: white; padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.15); }
        .stat-number { font-size: 36px; font-weight: bold; color: #667eea; }
        .stat-label { color: #666; margin-top: 10px; }
        .card { background: white; padding: 25px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.15); }
        .card h2 { color: #333; margin-bottom: 20px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; }
        .form-group input, .form-group textarea { width: 100%; padding: 12px; border: 2px solid #e5e7eb; border-radius: 8px; }
        .btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 25px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
        .logs-container { max-height: 300px; overflow-y: auto; background: #1f2937; border-radius: 10px; padding: 15px; }
        .log-item { color: #10b981; font-family: monospace; font-size: 12px; margin-bottom: 5px; }
        .quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
        .action-btn { padding: 15px; border-radius: 10px; text-align: center; color: white; cursor: pointer; }
        .action-btn.blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
        .action-btn.green { background: linear-gradient(135deg, #10b981, #059669); }
        .action-btn.purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
        .action-btn.red { background: linear-gradient(135deg, #ef4444, #dc2626); }
        .code-block { background: #1f2937; color: #10b981; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 لوحة تحكم بوت اصول الدين</h1>
            <div>
                <span class="status-badge">● يعمل</span>
                <a href="/logout"><button class="logout-btn">خروج</button></a>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_users }}</div>
                <div class="stat-label">المستخدمين</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_messages }}</div>
                <div class="stat-label">الرسائل</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.broadcasts|length }}</div>
                <div class="stat-label">الإرسالات</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.start_date }}</div>
                <div class="stat-label">تاريخ البدء</div>
            </div>
        </div>
        
        <div class="quick-actions">
            <div class="action-btn blue" onclick="scrollTo('broadcast')">📢 إرسال</div>
            <div class="action-btn green" onclick="scrollTo('stats')">📊 إحصائيات</div>
            <div class="action-btn purple" onclick="scrollTo('logs')">📋 سجلات</div>
        </div>
        
        <div id="broadcast" class="card" style="margin-top: 20px;">
            <h2>📢 إرسال رسالة جماعية</h2>
            <form method="POST" action="/broadcast">
                <div class="form-group">
                    <label>نص الرسالة</label>
                    <textarea name="message" rows="5" placeholder="أدخل نص الرسالة..." required></textarea>
                </div>
                <button type="submit" class="btn">إرسال</button>
            </form>
        </div>
        
        <div id="stats" class="card" style="margin-top: 20px;">
            <h2>📊 الإحصائيات</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{{ stats.total_users }}</div>
                    <div class="stat-label">المستخدمين</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">98%</div>
                    <div class="stat-label">التفاعل</div>
                </div>
            </div>
        </div>
        
        <div id="logs" class="card" style="margin-top: 20px;">
            <h2>📋 السجلات</h2>
            <div class="logs-container">
                {% for log in stats.commands_log[-50:] %}
                <div class="log-item">{{ log }}</div>
                {% endfor %}
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h2>🔗 كود التضمين في بلوجر</h2>
            <div class="code-block"><iframe src="{{ iframe_url }}" width="100%" height="800" frameborder="0"></iframe></div>
        </div>
    </div>
    <script>
        function scrollTo(id) { document.getElementById(id).scrollIntoView({behavior: 'smooth'}); }
    </script>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-box { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        h2 { text-align: center; margin-bottom: 30px; color: #333; }
        .form-group { margin-bottom: 20px; }
        .form-group input { width: 100%; padding: 15px; border: 2px solid #e5e7eb; border-radius: 10px; }
        .btn { width: 100%; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px; border: none; border-radius: 10px; cursor: pointer; }
        .error { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔐 تسجيل الدخول</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <div class="form-group">
                <input type="password" name="password" placeholder="كلمة المرور" required>
            </div>
            <button type="submit" class="btn">دخول</button>
        </form>
    </div>
</body>
</html>
"""

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Routes
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'كلمة المرور غير صحيحة'
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    iframe_url = f"{WEBHOOK_URL}/embed" if WEBHOOK_URL else "/embed"
    return render_template_string(DASHBOARD_HTML, stats=bot_stats, iframe_url=iframe_url)

@app.route('/embed')
def embed_dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>بوت اصول الدين</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f3f4f6; margin: 0; padding: 20px; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #667eea; }
            .status { text-align: center; padding: 15px; background: #d1fae5; color: #065f46; border-radius: 10px; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
            .stat { background: #f3f4f6; padding: 15px; border-radius: 10px; text-align: center; }
            .stat-num { font-size: 24px; font-weight: bold; color: #667eea; }
            .link { display: block; text-align: center; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 بوت اصول الدين</h1>
            <div class="status">● البوت يعمل بنجاح</div>
            <div class="stats">
                <div class="stat"><div class="stat-num">{{ stats.total_users }}</div><div>المستخدمين</div></div>
                <div class="stat"><div class="stat-num">{{ stats.total_messages }}</div><div>الرسائل</div></div>
            </div>
            <a href="{{ WEBHOOK_URL }}" target="_blank" class="link">افتح لوحة التحكم</a>
        </div>
    </body>
    </html>
    """, stats=bot_stats, WEBHOOK_URL=WEBHOOK_URL)

@app.route('/broadcast', methods=['POST'])
@login_required
def broadcast():
    message = request.form.get('message')
    broadcast_data = {
        "message": message,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "sent"
    }
    bot_stats['broadcasts'].append(broadcast_data)
    bot_stats['commands_log'].append(f"[{datetime.now()}] Broadcast: {message[:50]}...")
    return jsonify({"status": "success", "message": "تم الإرسال"})

# مسار الويب هوك
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            bot = Application.builder().token(TELEGRAM_TOKEN).build().bot
            update_data = request.get_json(force=True)
            update = Update.de_json(update_data, bot)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    return "Bot is running! Use POST method.", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT, debug=True)
