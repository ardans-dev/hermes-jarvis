#!/usr/bin/env python3
"""
Hermes Jarvis v4.0 - Multimodal Autonomous AI Assistant
Platform: Microsoft Azure VM (vm-hermes, East Asia)

New Superpowers (v4.0):
- Persistent Cognitive Memory & Multi-turn Context (SQLite hermes.db)
- Proactive Task Scheduler & Audio Reminders (/remind, /reminders)
- Daily Operational Audio Briefing (/briefing)
- Real-Time Live Web Search ($0 Zero-Cost DuckDuckGo & Wikipedia)
- Remote Cloud Terminal (/exec, /whoami, /claim) with Safety Guardrails
- Azure Neural Voice (id-ID-GadisNeural) via Direct REST API
- Multimodal Vision Engine (Photos, Stack Traces, Diagrams)
"""

import os
import re
import sys
import time
import base64
import logging
import sqlite3
import asyncio
import tempfile
import subprocess
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Telegram
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    Application,
)

import requests
import psutil

# Load Environment Variables from .env
load_dotenv()


def clean_env(val, default: str = "") -> str:
    if val is None:
        return default
    cleaned = str(val).strip().strip("'\"").strip()
    return cleaned if cleaned else default


TELEGRAM_BOT_TOKEN = clean_env(os.getenv("TELEGRAM_BOT_TOKEN"), "8947727712:AAH5JhPuu8X4GIfDPPCbUKVJ1BxJqLIfPRI")
OPENROUTER_API_KEY = clean_env(os.getenv("OPENROUTER_API_KEY"))

raw_owner = clean_env(os.getenv("OWNER_TELEGRAM_ID"))
try:
    OWNER_TELEGRAM_ID = int(raw_owner) if raw_owner else None
except ValueError:
    OWNER_TELEGRAM_ID = None

AZURE_SPEECH_KEY = clean_env(os.getenv("AZURE_SPEECH_KEY"))
AZURE_SPEECH_REGION = clean_env(os.getenv("AZURE_SPEECH_REGION"), "eastasia")
VOICE_NAME = clean_env(os.getenv("VOICE_NAME"), "id-ID-GadisNeural")
OPENROUTER_MODEL = clean_env(os.getenv("OPENROUTER_MODEL"), "openrouter/free")

# Auto-migrate deprecated models
if OPENROUTER_MODEL in ["google/gemini-2.0-flash-exp:free", "openrouter/auto", ""]:
    OPENROUTER_MODEL = "openrouter/free"

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("HermesJarvis")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermes.db")

SYSTEM_PROMPT = """
You are Hermes, an autonomous Jarvis-class personal AI companion and engineering partner for Ahmad Yardan Rasika (ardans-dev), a brilliant software engineering student specializing in backend systems, distributed cloud architecture, and artificial intelligence.
Tone & Personality:
- Professional, articulate, sharp, loyal, and technically elite (like Friday/Jarvis).
- Primary languages: Bahasa Indonesia (fluent, modern, respectful, yet friendly) and English for code/technical terminology.
- When analyzing code or architecture, be precise, concise, identify root causes instantly, and provide elegant solutions.
- Address Ardan respectfully as "Dan", "Ardan", atau "Tuan Ardan" saat kontekstual.
- If asked about your identity or hosting: You run 24/7 on Microsoft Azure (East Asia, Hong Kong) on an Ubuntu node.
"""

USER_SETTINGS = {
    "voice_mode": "smart",  # "smart", "always", "off"
}


# =====================================================================
# Database & Memory Layer (SQLite)
# =====================================================================
def init_db():
    """Initialize SQLite database tables for memory, history, and reminders."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                fact TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                remind_time TEXT,
                message TEXT,
                is_triggered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


def save_message(user_id: int, role: str, content: str):
    """Save conversation turn and trim history to last 30 messages."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
            # Keep only the last 30 messages
            c.execute("""
                DELETE FROM conversations WHERE id IN (
                    SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT -1 OFFSET 30
                )
            """, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving message to DB: {e}")


def get_conversation_history(user_id: int, limit: int = 8) -> list:
    """Retrieve recent conversation turns in chronological order."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT role, content FROM (
                    SELECT id, role, content FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
            """, (user_id, limit))
            rows = c.fetchall()
            return [{"role": r[0], "content": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        return []


def clear_conversation_history(user_id: int):
    """Reset conversation context for a user."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()


def add_memory_fact(user_id: int, fact: str) -> int:
    """Add a long-term fact to persistent memory."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO memories (user_id, fact) VALUES (?, ?)", (user_id, fact.strip()))
        conn.commit()
        return c.lastrowid


def get_memory_facts(user_id: int) -> list:
    """Retrieve all stored memory facts for a user."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, fact, created_at FROM memories WHERE user_id = ? ORDER BY id ASC", (user_id,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        return []


def delete_memory_fact(fact_id: int, user_id: int) -> bool:
    """Delete a specific memory fact."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (fact_id, user_id))
        conn.commit()
        return c.rowcount > 0


def add_reminder(user_id: int, chat_id: int, remind_dt: datetime, message: str) -> int:
    """Schedule a proactive reminder."""
    time_str = remind_dt.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO reminders (user_id, chat_id, remind_time, message) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, time_str, message.strip())
        )
        conn.commit()
        return c.lastrowid


def get_due_reminders() -> list:
    """Fetch all reminders that are due and haven't triggered."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, user_id, chat_id, message FROM reminders WHERE is_triggered = 0 AND remind_time <= ?",
                (now_str,)
            )
            return c.fetchall()
    except Exception as e:
        logger.error(f"Error querying due reminders: {e}")
        return []


def mark_reminder_done(reminder_id: int):
    """Mark reminder as completed."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE reminders SET is_triggered = 1 WHERE id = ?", (reminder_id,))
        conn.commit()


def get_pending_reminders(user_id: int) -> list:
    """Get active reminders for a user."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, remind_time, message FROM reminders WHERE user_id = ? AND is_triggered = 0 AND remind_time > ? ORDER BY remind_time ASC",
            (user_id, now_str)
        )
        return c.fetchall()


def get_db_setting(key: str, default: str = "") -> str:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = c.fetchone()
            return row[0] if row else default
    except Exception:
        return default


def set_db_setting(key: str, value: str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()


# Initialize DB on load
init_db()

# Load dynamic owner ID if present in DB
db_owner = get_db_setting("owner_telegram_id")
if db_owner and not OWNER_TELEGRAM_ID:
    try:
        OWNER_TELEGRAM_ID = int(db_owner)
    except ValueError:
        pass


# =====================================================================
# Security & Authorization
# =====================================================================
def is_authorized(user_id: int) -> bool:
    if OWNER_TELEGRAM_ID is None:
        return True
    authorized = (user_id == OWNER_TELEGRAM_ID)
    if not authorized:
        logger.warning(f"Unauthorized user {user_id} rejected (owner lock is {OWNER_TELEGRAM_ID})")
    return authorized


def escape_html(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def sanitize_text_for_speech(text: str) -> str:
    cleaned = re.sub(r"```[\s\S]*?```", " [Potongan kode saya sertakan di pesan teks] ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"[#*_~`]", "", cleaned)
    cleaned = re.sub(r"https?://\S+", " tautan terlampir ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:800]


# =====================================================================
# Web Search Engine ($0 Cost - DDG + Wikipedia API)
# =====================================================================
def search_web_api(query: str, max_results: int = 3) -> list:
    """Zero-cost, fast real-time search via DuckDuckGo & Wikipedia."""
    results = []
    
    # 1. DuckDuckGo Instant Answer API
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "HermesJarvis/4.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", "Summary"),
                    "snippet": data.get("AbstractText"),
                    "url": data.get("AbstractURL", "")
                })
            for topic in data.get("RelatedTopics", [])[:2]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": "Topic",
                        "snippet": topic.get("Text"),
                        "url": topic.get("FirstURL", "")
                    })
    except Exception as e:
        logger.warning(f"DuckDuckGo API search error: {e}")

    # 2. Wikipedia Search API
    try:
        wiki_url = f"https://id.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
        req = urllib.request.Request(wiki_url, headers={"User-Agent": "HermesJarvis/4.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("query", {}).get("search", [])[:2]:
                clean_snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()
                results.append({
                    "title": item.get("title"),
                    "snippet": clean_snippet,
                    "url": f"https://id.wikipedia.org/wiki/{urllib.parse.quote(item.get('title'))}"
                })
    except Exception as e:
        logger.warning(f"Wikipedia search error: {e}")

    return results[:max_results]


def should_search_web(text: str) -> bool:
    """Intelligently detect if prompt requires live web data."""
    triggers = [
        "cari info", "berita", "terbaru", "cuaca", "kurs", "kurs dollar",
        "siapa itu", "apa itu", "update terkini", "rilis terbaru", "tahun 2026",
        "harga", "trending", "jadwal", "search"
    ]
    lower = text.lower()
    return any(t in lower for t in triggers)


# =====================================================================
# Audio Pipeline: Azure Speech STT & TTS REST APIs
# =====================================================================
def convert_audio_to_wav(input_path: str, output_path: str) -> bool:
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            output_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0
    except Exception as e:
        logger.error(f"FFmpeg conversion error: {e}")
        return False


def speech_to_text(audio_wav_path: str) -> str:
    if not AZURE_SPEECH_KEY:
        logger.warning("AZURE_SPEECH_KEY not set.")
        return ""

    try:
        url = f"https://{AZURE_SPEECH_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=id-ID"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
        }

        with open(audio_wav_path, "rb") as f:
            audio_data = f.read()

        logger.info(f"Sending audio ({len(audio_data)} bytes) to Azure STT REST API...")
        res = requests.post(url, headers=headers, data=audio_data, timeout=25)
        if res.status_code == 200:
            data = res.json()
            display_text = data.get("DisplayText", "")
            logger.info(f"Azure STT recognized: '{display_text}'")
            return display_text
        else:
            logger.error(f"STT REST API error {res.status_code}: {res.text}")
            return ""
    except Exception as e:
        logger.error(f"STT Exception: {e}")
        return ""


def text_to_speech(text: str, output_ogg_path: str) -> bool:
    if not AZURE_SPEECH_KEY:
        return False

    try:
        url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "HermesJarvisBot",
        }

        speak_text = sanitize_text_for_speech(text)
        if not speak_text:
            speak_text = "Baik Dan, informasi lengkap telah saya sertakan di pesan teks."

        safe_text = (
            speak_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

        ssml = f"""<speak version='1.0' xml:lang='id-ID'>
<voice xml:lang='id-ID' name='{VOICE_NAME}'>
{safe_text}
</voice>
</speak>"""

        logger.info(f"Generating TTS audio for {len(speak_text)} chars via Azure REST API...")
        res = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=30)
        if res.status_code == 200:
            mp3_path = output_ogg_path + ".mp3"
            with open(mp3_path, "wb") as f:
                f.write(res.content)

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                mp3_path,
                "-c:a",
                "libopus",
                "-b:a",
                "32k",
                output_ogg_path,
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            success = os.path.exists(output_ogg_path) and os.path.getsize(output_ogg_path) > 0
            logger.info(f"TTS audio conversion: {'Success' if success else 'Failed'}")
            return success
        else:
            logger.error(f"TTS REST API error {res.status_code}: {res.text}")
            return False
    except Exception as e:
        logger.error(f"TTS Exception: {e}")
        return False


# =====================================================================
# LLM Gateway (OpenRouter with Free Fallbacks)
# =====================================================================
def call_openrouter(messages: list) -> str:
    if not OPENROUTER_API_KEY:
        return "⚠️ OPENROUTER_API_KEY belum dikonfigurasi di server."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://gentle-river-0f3a40500.3.azurestaticapps.net",
        "X-Title": "Hermes-Jarvis-Telegram",
    }

    candidate_models = [
        OPENROUTER_MODEL,
        "openrouter/free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-2-9b-it:free",
    ]
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        try:
            logger.info(f"Calling OpenRouter model: {model_name}...")
            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=35,
            )
            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    msg = data["choices"][0]["message"]
                    content = msg.get("content") or msg.get("reasoning")
                    if content:
                        logger.info(f"Received response from {model_name} ({len(content)} chars)")
                        return content.strip()
            logger.warning(f"Model {model_name} returned {res.status_code}: {res.text[:150]}")
        except Exception as e:
            logger.error(f"Error querying {model_name}: {e}")

    return "⚠️ Maaf Dan, gateway AI sedang mengalami antrean. Silakan coba kirim ulang pesannya sesaat lagi."


def build_system_context(user_id: int, query_text: str = "") -> str:
    """Assemble SYSTEM_PROMPT enriched with persistent memory facts & live web snippets."""
    context_prompt = SYSTEM_PROMPT.strip()

    # 1. Inject persistent memories
    facts = get_memory_facts(user_id)
    if facts:
        facts_list = "\n".join([f"• {f[1]}" for f in facts])
        context_prompt += f"\n\n[Persistent Memory - Facts You Remember About Ardan]:\n{facts_list}"

    # 2. Inject live web search snippets if applicable
    if query_text and should_search_web(query_text):
        logger.info(f"Auto-triggering live web search for: '{query_text}'")
        snippets = search_web_api(query_text, max_results=3)
        if snippets:
            search_str = "\n".join([f"- {s['title']}: {s['snippet']} (Source: {s['url']})" for s in snippets])
            context_prompt += f"\n\n[Real-Time Web Search Grounding Data]:\n{search_str}\n(Use this up-to-date data to inform your answer)."

    return context_prompt


# =====================================================================
# Background Scheduler Worker (Proactive Reminders Daemon)
# =====================================================================
async def reminder_worker(app: Application):
    """Asynchronous background worker checking due reminders every 15 seconds."""
    logger.info("⏰ Background Reminder Scheduler Daemon active.")
    while True:
        try:
            due_items = get_due_reminders()
            for rem_id, u_id, c_id, msg in due_items:
                logger.info(f"Triggering reminder {rem_id} for user {u_id}: '{msg}'")
                alert_text = (
                    f"⏰ <b>HERMES PROACTIVE REMINDER PROTOCOL</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Halo Dan, ada agenda penting yang sudah jatuh tempo:\n\n"
                    f"📌 <b>{escape_html(msg)}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Peringatan otomatis terjadwal selesai dieksekusi.</i>"
                )
                try:
                    await app.bot.send_message(chat_id=c_id, text=alert_text, parse_mode=ParseMode.HTML)
                    if USER_SETTINGS["voice_mode"] in ["smart", "always"] and AZURE_SPEECH_KEY:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            ogg_path = os.path.join(tmpdir, "remind.ogg")
                            tts_voice = f"Dan, pengingat untuk kamu: {msg}"
                            if text_to_speech(tts_voice, ogg_path):
                                with open(ogg_path, "rb") as vf:
                                    await app.bot.send_voice(
                                        chat_id=c_id,
                                        voice=vf,
                                        caption="🎙️ <i>Audio Alarm (Gadis Neural)</i>",
                                        parse_mode=ParseMode.HTML,
                                    )
                except Exception as send_err:
                    logger.error(f"Error sending proactive reminder: {send_err}")
                finally:
                    mark_reminder_done(rem_id)
        except Exception as loop_err:
            logger.error(f"Exception in reminder_worker: {loop_err}")

        await asyncio.sleep(15)


async def on_startup(app: Application):
    """Post-initialization hook to spawn background daemon."""
    asyncio.create_task(reminder_worker(app))


# =====================================================================
# Helper: Parse Reminder Time
# =====================================================================
def parse_remind_time(time_str: str) -> datetime:
    now = datetime.now()
    # Relative time: 10s, 5m, 2h, 1d
    match_rel = re.match(r"^(\d+)([smhd])$", time_str.lower())
    if match_rel:
        val, unit = int(match_rel.group(1)), match_rel.group(2)
        if unit == "s":
            return now + timedelta(seconds=val)
        elif unit == "m":
            return now + timedelta(minutes=val)
        elif unit == "h":
            return now + timedelta(hours=val)
        elif unit == "d":
            return now + timedelta(days=val)

    # Time of day: HH:MM
    match_time = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if match_time:
        hour, minute = int(match_time.group(1)), int(match_time.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    return None


# =====================================================================
# Telegram Command Handlers
# =====================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Incoming /start from user {user.id} ({user.first_name})")

    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    welcome = (
        "⚡ <b>HERMES JARVIS ONLINE [v4.0.0-Azure]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Halo Dan! Sistem Jarvis pribadi kamu kini telah di-upgrade dengan memori cerdas dan kemampuan otonom penuh.\n\n"
        "🎙️ <b>Kemampuan Suara (Voice-to-Voice):</b>\n"
        "Kirim Voice Note kapan saja. Saya akan membalas langsung dengan rekaman suara natural <b>Azure Neural Voice (`id-ID-GadisNeural`)</b>.\n\n"
        "👁️ <b>Multimodal Vision Engine:</b>\n"
        "Kirim foto atau tangkapan layar kode error, diagram arsitektur, atau slide materi kuliah.\n\n"
        "🧠 <b>Fitur Memori & Produktivitas:</b>\n"
        "• <code>/remember [fakta]</code> - Simpan catatan penting ke memori jangka panjang\n"
        "• <code>/memory</code> - Buka berkas memori yang tersimpan\n"
        "• <code>/remind [waktu] [tugas]</code> - Pasang pengingat otomatis (contoh: <code>/remind 30m Cek server</code>)\n"
        "• <code>/briefing</code> - Dengarkan ringkasan operasional harian\n"
        "• <code>/search [kata kunci]</code> - Pencarian web real-time ($0 gratis)\n"
        "• <code>/exec [perintah]</code> - Kontrol terminal Azure VM langsung dari chat\n"
        "• <code>/status</code> - Pantau CPU, RAM, Disk, dan Uptime VM\n"
        "• <code>/clear</code> - Bersihkan riwayat percakapan saat ini\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>'Standing by for your command, Dan.'</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Incoming /status request from user {user.id} ({user.first_name})")

    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    mem_count = len(get_memory_facts(user.id))
    rem_count = len(get_pending_reminders(user.id))

    status = (
        "📡 <b>AZURE CLOUD TELEMETRY: vm-hermes</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Region:</b> East Asia (Hong Kong)\n"
        f"⚡ <b>Compute:</b> Standard_B2ats_v2 (AMD EPYC)\n"
        f"⏱ <b>Uptime:</b> {hours}j {minutes}m {seconds}d\n\n"
        f"📊 <b>CPU Load:</b> {cpu_pct}%\n"
        f"🧠 <b>RAM:</b> {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
        f"💾 <b>Swap:</b> {swap.percent}% ({swap.used // (1024**2)}MB / {swap.total // (1024**2)}MB)\n"
        f"📁 <b>Disk:</b> {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)\n\n"
        f"🎙️ <b>Neural Speech:</b> {'ONLINE (Gadis)' if AZURE_SPEECH_KEY else 'STANDBY'}\n"
        f"🔊 <b>Voice Mode:</b> {USER_SETTINGS['voice_mode'].upper()}\n"
        f"🤖 <b>AI Model:</b> {OPENROUTER_MODEL} (100% Free)\n"
        f"🧠 <b>Stored Memories:</b> {mem_count} fakta tersimpan\n"
        f"⏰ <b>Pending Reminders:</b> {rem_count} pengingat aktif\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Semua sub-sistem beroperasi normal ($0).</i>"
    )

    try:
        await update.message.reply_text(status, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Failed to send HTML status ({e}), sending plain text...")
        clean_text = re.sub(r"<[^>]+>", "", status)
        await update.message.reply_text(clean_text)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    args = context.args
    if not args or args[0].lower() not in ["on", "off", "smart"]:
        current = USER_SETTINGS["voice_mode"]
        await update.message.reply_text(
            f"ℹ️ Mode suara saat ini: <b>{current.upper()}</b>\n\n"
            "Gunakan perintah:\n"
            "• <code>/voice smart</code> - Balas VN jika ditanya via VN (Rekomendasi)\n"
            "• <code>/voice on</code> - Selalu membalas dengan Voice Note\n"
            "• <code>/voice off</code> - Mode hening (balas teks saja)",
            parse_mode=ParseMode.HTML,
        )
        return

    mode = args[0].lower()
    USER_SETTINGS["voice_mode"] = mode
    await update.message.reply_text(
        f"✅ Mode suara berhasil diubah ke: <b>{mode.upper()}</b>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save a fact to persistent memory."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ <b>Format Perintah:</b>\n<code>/remember [fakta atau catatan]</code>\n\n"
            "<i>Contoh:</i>\n"
            "• <code>/remember Saya sedang mengerjakan tugas proyek akhir arsitektur microservices</code>\n"
            "• <code>/remember Ujian Basis Data dilaksanakan tanggal 12 September</code>",
            parse_mode=ParseMode.HTML
        )
        return

    fact_text = " ".join(context.args).strip()
    fact_id = add_memory_fact(user.id, fact_text)
    await update.message.reply_text(
        f"🧠 <b>Memori Tersimpan! [ID: #{fact_id}]</b>\n"
        f"Saya akan selalu mengingat: <i>\"{escape_html(fact_text)}\"</i> di percakapan berikutnya.",
        parse_mode=ParseMode.HTML
    )


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View stored persistent memories."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    facts = get_memory_facts(user.id)
    if not facts:
        await update.message.reply_text(
            "🧠 Belum ada memori yang tersimpan.\n"
            "Gunakan <code>/remember [fakta]</code> untuk menambahkan pengetahuan baru yang harus saya ingat.",
            parse_mode=ParseMode.HTML
        )
        return

    lines = [f"• <b>[#{f[0]}]</b> {escape_html(f[1])} <span class='text-xs'>({f[2][:10]})</span>" for f in facts]
    reply = (
        "🧠 <b>BERKAS MEMORI KOGNITIF HERMES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Gunakan <code>/forget [id]</code> untuk menghapus memori tertentu.</i>"
    )
    await update.message.reply_text(reply, parse_mode=ParseMode.HTML)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a memory fact."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Gunakan <code>/forget [ID]</code>. Contoh: <code>/forget 1</code>", parse_mode=ParseMode.HTML)
        return

    try:
        fact_id = int(context.args[0])
        if delete_memory_fact(fact_id, user.id):
            await update.message.reply_text(f"🗑️ Memori [#{fact_id}] berhasil dihapus.")
        else:
            await update.message.reply_text(f"⚠️ Memori dengan ID #{fact_id} tidak ditemukan.")
    except ValueError:
        await update.message.reply_text("⚠️ ID memori harus berupa angka.")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation history (keep persistent memories)."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    clear_conversation_history(user.id)
    await update.message.reply_text("🧹 Riwayat percakapan telah dibersihkan. Memori jangka panjang tetap aman!")


async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule a task reminder."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "ℹ️ <b>Format Pengingat:</b>\n"
            "<code>/remind [durasi/jam] [pesan tugas]</code>\n\n"
            "<i>Contoh Waktu Relatif:</i>\n"
            "• <code>/remind 10m Cek progress deployment Azure</code>\n"
            "• <code>/remind 1h Istirahat dan minum air</code>\n"
            "• <code>/remind 30s Tes pengingat cepat</code>\n\n"
            "<i>Contoh Jam Spesifik:</i>\n"
            "• <code>/remind 08:00 Kelas Pemrograman Berorientasi Objek</code>",
            parse_mode=ParseMode.HTML
        )
        return

    time_str = context.args[0]
    task_text = " ".join(context.args[1:])

    target_dt = parse_remind_time(time_str)
    if not target_dt:
        await update.message.reply_text("⚠️ Format waktu tidak valid. Gunakan format seperti `10m`, `1h`, `30s`, atau `14:30`.")
        return

    rem_id = add_reminder(user.id, update.effective_chat.id, target_dt, task_text)
    time_fmt = target_dt.strftime("%d/%m/%Y pukul %H:%M:%S")
    await update.message.reply_text(
        f"⏰ <b>Pengingat Berhasil Dijadwalkan! [#{rem_id}]</b>\n"
        f"📌 <b>Tugas:</b> {escape_html(task_text)}\n"
        f"⏱ <b>Akan Berbunyi:</b> {time_fmt} WIB\n\n"
        f"<i>Saya akan mengirimkan notifikasi teks dan audio saat waktunya tiba.</i>",
        parse_mode=ParseMode.HTML
    )


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending scheduled reminders."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    rems = get_pending_reminders(user.id)
    if not rems:
        await update.message.reply_text("⏰ Tidak ada pengingat yang sedang aktif.\nPasang pengingat baru dengan <code>/remind [waktu] [pesan]</code>.", parse_mode=ParseMode.HTML)
        return

    lines = [f"• <b>[#{r[0]}]</b> {escape_html(r[2])} &rarr; <code>{r[1]} WIB</code>" for r in rems]
    reply = (
        "⏰ <b>DAFTAR PENGINGAT AKTIF</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
        + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(reply, parse_mode=ParseMode.HTML)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explicit real-time web search."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("ℹ️ Gunakan <code>/search [kata kunci yang dicari]</code>", parse_mode=ParseMode.HTML)
        return

    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text(f"🔍 <i>Menjelajahi web untuk \"{escape_html(query)}\"...</i>", parse_mode=ParseMode.HTML)

    snippets = search_web_api(query, max_results=4)
    if not snippets:
        await status_msg.edit_text("⚠️ Tidak ditemukan hasil pencarian yang relevan di web.")
        return

    web_context = "\n".join([f"- {s['title']}: {s['snippet']} (Link: {s['url']})" for s in snippets])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\n\n[Live Web Results]:\n{web_context}\nBerikan ringkasan yang tajam, akurat, dan cantumkan link sumbernya."},
        {"role": "user", "content": f"Berdasarkan informasi web terkini, jelaskan mengenai: {query}"}
    ]

    ai_reply = call_openrouter(messages)
    try:
        await status_msg.delete()
    except Exception:
        pass

    await update.message.reply_text(ai_reply)


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate instant operational daily briefing with voice note."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text("⚡ <i>Menyiapkan Daily Briefing untukmu, Dan...</i>", parse_mode=ParseMode.HTML)

    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y - %H:%M WIB")

    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    rems = get_pending_reminders(user.id)
    rem_summary = ", ".join([r[2] for r in rems]) if rems else "Tidak ada agenda mendesak"

    briefing_prompt = f"""
Current Date/Time: {date_str}
System Status: Azure VM vm-hermes (CPU: {cpu_pct}%, RAM: {mem.percent}% used).
Pending Tasks/Reminders: {rem_summary}

Instructions:
Generate a crisp, elite, motivational Jarvis-style morning/evening operational briefing for Ardan in Bahasa Indonesia.
Address him respectfully as Dan. Mention the time, acknowledge that his cloud nodes are operating nominally, summarize his agenda, and deliver a motivating closing thought for his engineering journey.
Keep it under 150 words so it speaks smoothly.
"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": briefing_prompt},
    ]
    ai_reply = call_openrouter(messages)

    # Synthesize speech
    with tempfile.TemporaryDirectory() as tmpdir:
        ogg_path = os.path.join(tmpdir, "briefing.ogg")
        has_tts = text_to_speech(ai_reply, ogg_path)

        try:
            await status_msg.delete()
        except Exception:
            pass

        if has_tts and os.path.exists(ogg_path):
            with open(ogg_path, "rb") as vf:
                await context.bot.send_voice(
                    chat_id=chat_id,
                    voice=vf,
                    caption=f"🎙️ <i>Hermes Operational Briefing • {now.strftime('%d/%m/%Y')}</i>",
                    parse_mode=ParseMode.HTML
                )

        await update.message.reply_text(ai_reply)


async def cmd_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute safe remote bash command on Azure VM (Owner only)."""
    user = update.effective_user
    global OWNER_TELEGRAM_ID

    # Strict authorization
    if OWNER_TELEGRAM_ID and user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("⛔ Access Denied: Eksekusi terminal hanya diizinkan untuk Operator Utama.")
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ <b>Remote Cloud Terminal Executor:</b>\n"
            "<code>/exec [perintah bash]</code>\n\n"
            "<i>Contoh Aman:</i>\n"
            "• <code>/exec uptime</code>\n"
            "• <code>/exec free -h</code>\n"
            "• <code>/exec pm2 status</code>\n"
            "• <code>/exec docker ps</code>\n"
            "• <code>/exec git status</code>",
            parse_mode=ParseMode.HTML
        )
        return

    cmd_text = " ".join(context.args)

    # Danger filter
    dangerous = [r"rm\s+-rf\s+/", r"mkfs", r":\(\)\{", r">\s*/dev/sd"]
    for pat in dangerous:
        if re.search(pat, cmd_text):
            await update.message.reply_text("🚫 Perintah berisiko tinggi diblokir oleh protokol keamanan Jarvis.")
            return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    try:
        res = subprocess.run(
            cmd_text,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25,
            cwd=os.path.expanduser("~")
        )
        output = res.stdout if res.stdout else res.stderr
        if not output:
            output = "[Command executed successfully with zero stdout]"

        if len(output) > 3500:
            output = output[:3500] + "\n... [Truncated for Telegram limit]"

        status_emoji = "✅" if res.returncode == 0 else "⚠️"
        reply = (
            f"{status_emoji} <b>Bash Output (Exit Code: {res.returncode}):</b>\n"
            f"<pre><code>{escape_html(output)}</code></pre>"
        )
        await update.message.reply_text(reply, parse_mode=ParseMode.HTML)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Perintah dihentikan karena melebihi batas waktu (timeout 25 detik).")
    except Exception as e:
        await update.message.reply_text(f"❌ Error eksekusi: {e}")


async def cmd_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim ownership of the bot."""
    user = update.effective_user
    global OWNER_TELEGRAM_ID

    if OWNER_TELEGRAM_ID and user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("⛔ Bot ini sudah dimiliki oleh operator lain.")
        return

    OWNER_TELEGRAM_ID = user.id
    set_db_setting("owner_telegram_id", str(user.id))
    await update.message.reply_text(
        f"👑 <b>Kepemilikan Berhasil Diklaim!</b>\n"
        f"Operator: <b>{escape_html(user.first_name)}</b> (<code>{user.id}</code>)\n"
        f"Akses terminal remote (<code>/exec</code>) kini aktif secara eksklusif untuk akunmu.",
        parse_mode=ParseMode.HTML
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user ID and authorization level."""
    user = update.effective_user
    is_owner = (OWNER_TELEGRAM_ID and user.id == OWNER_TELEGRAM_ID)
    reply = (
        f"👤 <b>Telegram Identity Dossier:</b>\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        f"• <b>Nama:</b> {escape_html(user.first_name)}\n"
        f"• <b>Username:</b> @{user.username if user.username else '-'}\n"
        f"• <b>Status Akses:</b> {'👑 Verified Owner (Root Access)' if is_owner else ('🟢 Unrestricted' if OWNER_TELEGRAM_ID is None else '🔒 Standard User')}\n\n"
        f"<i>Gunakan <code>/claim</code> untuk mengunci bot ke ID ini.</i>"
    )
    await update.message.reply_text(reply, parse_mode=ParseMode.HTML)


# =====================================================================
# Message Handlers (Voice, Photo, Text) with Cognitive Memory
# =====================================================================
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Incoming voice message from user {user.id} ({user.first_name})")

    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_audio_path = os.path.join(tmpdir, "incoming.audio")
        wav_path = os.path.join(tmpdir, "incoming.wav")
        response_ogg_path = os.path.join(tmpdir, "response.ogg")

        voice_file = await context.bot.get_file(voice.file_id)
        await voice_file.download_to_drive(input_audio_path)

        if not convert_audio_to_wav(input_audio_path, wav_path):
            await update.message.reply_text("⚠️ Gagal memproses audio input via FFmpeg.")
            return

        transcription = speech_to_text(wav_path)
        if not transcription:
            await update.message.reply_text(
                "🎙️ Maaf Dan, suara belum terdeteksi jelas. Boleh dicoba kirim ulang ya!"
            )
            return

        status_msg = await update.message.reply_text(
            f"<i>🎙️ Mendengar: \"{transcription}\"</i>\n⏳ <i>Memproses...</i>",
            parse_mode=ParseMode.HTML,
        )

        # Multi-turn history & context enrichment
        save_message(user.id, "user", transcription)
        system_ctx = build_system_context(user.id, transcription)
        history = get_conversation_history(user.id, limit=8)

        messages = [{"role": "system", "content": system_ctx}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        ai_response = call_openrouter(messages)
        save_message(user.id, "assistant", ai_response)

        should_voice = USER_SETTINGS["voice_mode"] in ["smart", "always"]
        has_tts = False

        if should_voice and AZURE_SPEECH_KEY:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
            has_tts = text_to_speech(ai_response, response_ogg_path)

        try:
            await status_msg.delete()
        except Exception:
            pass

        if has_tts and os.path.exists(response_ogg_path):
            with open(response_ogg_path, "rb") as f:
                await context.bot.send_voice(
                    chat_id=chat_id,
                    voice=f,
                    caption="🎙️ <i>Hermes Voice Response (Gadis Neural)</i>",
                    parse_mode=ParseMode.HTML,
                )

        await update.message.reply_text(ai_response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Incoming photo from user {user.id} ({user.first_name})")

    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]
    caption = update.message.caption or "Tolong analisis gambar/kode/arsitektur ini secara mendalam dan berikan penjelasan teknis."

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text(
        "👁️ <i>Memindai gambar dengan Vision Engine...</i>",
        parse_mode=ParseMode.HTML,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "photo.jpg")
        photo_file = await context.bot.get_file(photo.file_id)
        await photo_file.download_to_drive(img_path)

        with open(img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_data}"

        system_ctx = build_system_context(user.id, caption)
        messages = [
            {"role": "system", "content": system_ctx},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

        ai_response = call_openrouter(messages)
        save_message(user.id, "user", f"[Photo with caption]: {caption}")
        save_message(user.id, "assistant", ai_response)

        try:
            await status_msg.delete()
        except Exception:
            pass

        if USER_SETTINGS["voice_mode"] == "always" and AZURE_SPEECH_KEY:
            resp_ogg = os.path.join(tmpdir, "resp.ogg")
            if text_to_speech(ai_response, resp_ogg):
                with open(resp_ogg, "rb") as vf:
                    await context.bot.send_voice(chat_id=chat_id, voice=vf)

        await update.message.reply_text(ai_response)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_text = update.message.text
    logger.info(f"Incoming text: '{user_text}' from user {user.id} ({user.first_name})")

    if not is_authorized(user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Multi-turn history & context enrichment
    save_message(user.id, "user", user_text)
    system_ctx = build_system_context(user.id, user_text)
    history = get_conversation_history(user.id, limit=8)

    messages = [{"role": "system", "content": system_ctx}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    ai_response = call_openrouter(messages)
    save_message(user.id, "assistant", ai_response)

    if USER_SETTINGS["voice_mode"] == "always" and AZURE_SPEECH_KEY:
        with tempfile.TemporaryDirectory() as tmpdir:
            resp_ogg = os.path.join(tmpdir, "resp.ogg")
            if text_to_speech(ai_response, resp_ogg):
                with open(resp_ogg, "rb") as vf:
                    await context.bot.send_voice(chat_id=chat_id, voice=vf)

    await update.message.reply_text(ai_response)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(f"⚠️ Terjadi error internal: {context.error}")
        except Exception:
            pass


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found!")
        sys.exit(1)

    logger.info("⚡ Initializing Hermes Jarvis Engine (v4.0.0)...")
    logger.info(f"OpenRouter Model: {OPENROUTER_MODEL}")
    logger.info(f"Azure Speech: Region={AZURE_SPEECH_REGION}, Voice={VOICE_NAME}")
    logger.info(f"Owner Lock: {'LOCKED to ' + str(OWNER_TELEGRAM_ID) if OWNER_TELEGRAM_ID else 'DYNAMIC / UNRESTRICTED'}")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_error_handler(global_error_handler)

    # Core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("voice", cmd_voice))

    # Cognitive memory & context
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("reset", cmd_clear))

    # Task scheduler & daily briefing
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CommandHandler("reminders", cmd_reminders))
    app.add_handler(CommandHandler("briefing", cmd_briefing))

    # Live web search & cloud terminal
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("exec", cmd_exec))
    app.add_handler(CommandHandler("claim", cmd_claim))
    app.add_handler(CommandHandler("whoami", cmd_whoami))

    # Message handlers
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 Hermes Jarvis v4.0 Online. Polling Telegram updates...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
