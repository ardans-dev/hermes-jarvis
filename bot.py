#!/usr/bin/env python3
"""
Hermes Jarvis - Multimodal Autonomous AI Assistant for Telegram
Platform: Microsoft Azure (East Asia)

Features:
- Free OpenRouter Model (openrouter/free, openrouter/auto)
- Azure Neural Voice TTS (id-ID-GadisNeural) via REST API (100% cloud resilient)
- Azure Speech STT (id-ID) via REST API (100% headless server compatible)
- Multimodal Vision Engine (Photos, Code, Diagrams)
- Live Telemetry (/status)
"""

import os
import re
import sys
import time
import base64
import logging
import tempfile
import subprocess
from datetime import datetime
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
)

import requests
import psutil

# Load Environment Variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "").strip()
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastasia").strip()
VOICE_NAME = os.getenv("VOICE_NAME", "id-ID-GadisNeural").strip()
# Use free model router
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("HermesJarvis")

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


def is_authorized(user_id: int) -> bool:
    if not OWNER_TELEGRAM_ID:
        return True
    return str(user_id).strip() == str(OWNER_TELEGRAM_ID).strip()


def sanitize_text_for_speech(text: str) -> str:
    cleaned = re.sub(r"```[\s\S]*?```", " [Potongan kode saya sertakan di pesan teks] ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"[#*_~`]", "", cleaned)
    cleaned = re.sub(r"https?://\S+", " tautan terlampir ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:800]


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
        logger.error(f"FFmpeg error: {e}")
        return False


def speech_to_text(audio_wav_path: str) -> str:
    """Transcribe speech via Azure Speech REST API."""
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

        res = requests.post(url, headers=headers, data=audio_data, timeout=25)
        if res.status_code == 200:
            data = res.json()
            if data.get("RecognitionStatus") == "Success":
                return data.get("DisplayText", "")
            else:
                logger.info(f"STT status: {data.get('RecognitionStatus')}")
                return ""
        else:
            logger.error(f"STT REST API error {res.status_code}: {res.text}")
            return ""
    except Exception as e:
        logger.error(f"STT Exception: {e}")
        return ""


def text_to_speech(text: str, output_ogg_path: str) -> bool:
    """Synthesize speech via Azure Speech REST API + FFmpeg to OGG Opus."""
    if not AZURE_SPEECH_KEY:
        return False

    try:
        url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
            "User-Agent": "HermesJarvis",
        }

        speak_text = sanitize_text_for_speech(text)
        if not speak_text:
            speak_text = "Baik Dan, informasi lengkap telah saya tampilkan di pesan teks."

        # Escape XML characters
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

        res = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=25)
        if res.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                tmp_mp3.write(res.content)
                mp3_path = tmp_mp3.name

            # Convert to OGG Opus for native Telegram voice bubble
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
            return os.path.exists(output_ogg_path) and os.path.getsize(output_ogg_path) > 0
        else:
            logger.error(f"TTS REST API error {res.status_code}: {res.text}")
            return False
    except Exception as e:
        logger.error(f"TTS Exception: {e}")
        return False


def call_openrouter(messages: list) -> str:
    """Query OpenRouter with automatic fallback on free models."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://gentle-river-0f3a40500.3.azurestaticapps.net",
        "X-Title": "Hermes-Jarvis-Telegram",
    }

    # List of models to try in order (always free)
    candidate_models = [OPENROUTER_MODEL, "openrouter/free", "openrouter/auto"]
    # De-duplicate while preserving order
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
                        return content.strip()
            logger.warning(f"Model {model_name} failed with status {res.status_code}: {res.text[:150]}")
        except Exception as e:
            logger.error(f"Error querying {model_name}: {e}")

    return "⚠️ Maaf Dan, gateway AI sedang mengalami antrean. Silakan coba kirim ulang pesannya sesaat lagi."


# Handlers
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    welcome = (
        "⚡ <b>HERMES JARVIS ONLINE [v3.1.0-Azure]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Halo Dan! Sistem Jarvis pribadi kamu sudah aktif dan siap beroperasi.\n\n"
        "🎙️ <b>Kemampuan Suara (Voice-to-Voice):</b>\n"
        "Kirim Voice Note kapan saja. Saya akan mendengarkan dan membalas balik dengan suara Gadis Neural berbahasa Indonesia natural.\n\n"
        "👁️ <b>Kemampuan Penglihatan (Vision):</b>\n"
        "Kirim foto kode error, screenshot terminal, atau slide kuliah. Saya akan menganalisis dan memberikan solusinya.\n\n"
        "🛠️ <b>Perintah Operasional:</b>\n"
        "• <code>/status</code> - Cek telemetri live node Azure VM\n"
        "• <code>/voice [smart|on|off]</code> - Atur preferensi balasan suara\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>'Standing by for your command, Dan.'</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    cpu_pct = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    status = (
        "📡 <b>AZURE CLOUD TELEMETRY: vm-hermes</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Region:</b> East Asia (Hong Kong)\n"
        f"⚡ <b>Compute:</b> Standard_B2ats_v2 (AMD EPYC)\n"
        f"⏱ <b>Uptime:</b> {hours}j {minutes}m {seconds}d\n\n"
        f"📊 <b>CPU Load:</b> {cpu_pct}%\n"
        f"🧠 <b>RAM:</b> {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
        f"💾 <b>Swap:</b> {swap.percent}% ({swap.used // (1024**2)}MB / {swap.total // (1024**2)}MB)\n"
        f"📁 <b>Disk:</b> {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)\n"
        f"🎙️ <b>Neural Speech Engine:</b> {'ONLINE' if AZURE_SPEECH_KEY else 'STANDBY'}\n"
        f"🔊 <b>Voice Mode:</b> {USER_SETTINGS['voice_mode'].upper()}\n"
        f"🤖 <b>AI Model:</b> {OPENROUTER_MODEL} (100% Free)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Semua sub-sistem beroperasi normal ($0).</i>"
    )
    await update.message.reply_text(status, parse_mode=ParseMode.HTML)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
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


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
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
                "🎙️ Maaf Dan, suara kurang terdengar jelas atau belum terdeteksi. Boleh coba kirim ulang ya!"
            )
            return

        status_msg = await update.message.reply_text(
            f"<i>🎙️ Mendengar: \"{transcription}\"</i>\n⏳ <i>Memproses...</i>",
            parse_mode=ParseMode.HTML,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcription},
        ]
        ai_response = call_openrouter(messages)

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
    if not is_authorized(update.effective_user.id):
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

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

        ai_response = call_openrouter(messages)

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
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Access Denied.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    ai_response = call_openrouter(messages)

    if USER_SETTINGS["voice_mode"] == "always" and AZURE_SPEECH_KEY:
        with tempfile.TemporaryDirectory() as tmpdir:
            resp_ogg = os.path.join(tmpdir, "resp.ogg")
            if text_to_speech(ai_response, resp_ogg):
                with open(resp_ogg, "rb") as vf:
                    await context.bot.send_voice(chat_id=chat_id, voice=vf)

    await update.message.reply_text(ai_response)


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found!")
        sys.exit(1)

    logger.info("⚡ Initializing Hermes Jarvis Engine (v3.1.0)...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("voice", cmd_voice))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 Hermes Jarvis Online. Polling Telegram updates...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
