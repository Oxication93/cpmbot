import logging, sqlite3, httpx
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
FIREBASE_API_KEY = os.environ.get("FIREBASE_KEY", "AIzaSyD9example123")

app2 = Flask('')
@app2.route('/')
def home(): return "läuft"
Thread(target=lambda: app2.run(host='0.0.0.0', port=8080)).start()

logging.basicConfig(level=logging.INFO)

def db_init():
    con = sqlite3.connect("acc.db")
    con.execute("CREATE TABLE IF NOT EXISTS acc (id INTEGER PRIMARY KEY, uid INTEGER, name TEXT, token TEXT, refresh TEXT, date TEXT)")
    con.commit(); con.close()

def db_save(uid, name, token, refresh):
    con = sqlite3.connect("acc.db")
    con.execute("INSERT INTO acc (uid,name,token,refresh,date) VALUES (?,?,?,?,?)", (uid,name,token,refresh,datetime.utcnow().isoformat()))
    con.commit(); con.close()

def db_list(uid):
    con = sqlite3.connect("acc.db")
    rows = con.execute("SELECT id,name,token,refresh FROM acc WHERE uid=?",(uid,)).fetchall()
    con.close(); return rows

def db_del(aid, uid):
    con = sqlite3.connect("acc.db")
    con.execute("DELETE FROM acc WHERE id=? AND uid=?",(aid,uid))
    con.commit(); con.close()

async def refresh_token(refresh):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
            data={"grant_type":"refresh_token","refresh_token":refresh},timeout=10)
    return r.json() if r.status_code==200 else None

async def get_profile(id_token):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}",
            json={"idToken":id_token},timeout=10)
    if r.status_code==200:
        u=r.json().get("users",[])
        return u[0] if u else None
    return None

WAIT=1

async def start(update: Update, ctx):
    kb=[[InlineKeyboardButton("➕ Account hinzufügen",callback_data="add")],
        [InlineKeyboardButton("📋 Meine Accounts",callback_data="list")],
        [InlineKeyboardButton("❓ Wie Token holen?",callback_data="help")]]
    await update.message.reply_text("🚗 *CPM Klon Bot*\n\nWas möchtest du tun?",
        parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))

async def btn(update: Update, ctx):
    q=update.callback_query
    await q.answer()
    uid=update.effective_user.id
    if q.data=="add":
        await q.message.reply_text("🔑 Schick mir deinen Firebase *refreshToken*",parse_mode="Markdown")
        return WAIT
    elif q.data=="list":
        rows=db_list(uid)
        if not rows:
            await q.message.reply_text("📭 Keine Accounts. Tippe /start")
            return
        for r in rows:
            kb=[[InlineKeyboardButton("📦 Clone-Daten",callback_data=f"clone_{r[0]}"),
                 InlineKeyboardButton("🗑 Löschen",callback_data=f"del_{r[0]}")]]
            await q.message.reply_text(f"👤 *{r[1]}*",parse_mode="Markdown",reply_markup=InlineKeyboardMarkup(kb))
    elif q.data=="help":
        await q.message.reply_text(
            "📖 *Token holen — Mit Root:*\n\n"
            "1. MT Manager installieren\n"
            "2. Öffnen → `/` → `data` → `data`\n"
            "3. → `com.olzhass.carparking` → `shared_prefs`\n"
            "4. Firebase XML öffnen\n"
            "5. REFRESH\_TOKEN kopieren ✅",
            parse_mode="Markdown")
    elif q.data.startswith("clone_"):
        aid=int(q.data.split("_")[1])
        rows=db_list(uid)
        acc=next((r for r in rows if r[0]==aid),None)
        if acc:
            await q.message.reply_text(
                f"📦 *Clone-Daten*\n\n*refreshToken:*\n`{acc[3]}`\n\n"
                f"📲 Auf Gerät 2:\nMT Manager → com.olzhass.carparking\n→ shared\_prefs → Firebase XML\n→ Token ersetzen → CPM starten ✅",
                parse_mode="Markdown")
    elif q.data.startswith("del_"):
        db_del(int(q.data.split("_")[1]),uid)
        await q.message.reply_text("✅ Gelöscht.")
    return ConversationHandler.END

async def recv(update: Update, ctx):
    refresh=update.message.text.strip()
    uid=update.effective_user.id
    msg=await update.message.reply_text("🔄 Überprüfe Token…")
    data=await refresh_token(refresh)
    if not data:
        await msg.edit_text("❌ Ungültiger Token.")
        return ConversationHandler.END
    profile=await get_profile(data.get("id_token",""))
    name="Unbekannt"
    if profile:
        name=profile.get("displayName") or profile.get("email") or profile.get("localId","")[:10]
    db_save(uid,name,data.get("id_token",""),data.get("refresh_token",refresh))
    await msg.edit_text(f"✅ *Gespeichert!*\n\n👤 `{name}`\n\nTippe /start → Meine Accounts",parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, ctx):
    await update.message.reply_text("Abgebrochen.")
    return ConversationHandler.END

def main():
    db_init()
    application=Application.builder().token(BOT_TOKEN).build()
    conv=ConversationHandler(
        entry_points=[CallbackQueryHandler(btn,pattern="^add$")],
        states={WAIT:[MessageHandler(filters.TEXT & ~filters.COMMAND,recv)]},
        fallbacks=[CommandHandler("cancel",cancel)])
    application.add_handler(CommandHandler("start",start))
    application.add_handler(conv)
    application.add_handler(CallbackQueryHandler(btn))
    print("Bot läuft…")
    application.run_polling()

main()
