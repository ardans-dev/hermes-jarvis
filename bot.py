#!/usr/bin/env python3
"""
Hermes Jarvis - Multimodal Autonomous AI Assistant for Telegram
Created for: Ahmad Yardan Rasika (ardans-dev)
Platform: Microsoft Azure (East Asia)

Capabilities:
1. Voice-to-Voice: Azure AI Speech STT & Neural TTS (id-ID-GadisNeural).
2. Computer Vision: Multimodal image analysis (Code, Diagrams, Screenshots).
3. Cloud Telemetry: Real-time CPU, RAM, Swap, Disk & Uptime metrics.
4. Security: Whitelist User ID locked.
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

# Telegram Imports
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Third-party Imports
import requests
import psutil

# Azure Speech SDK
try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

# Load Environment Variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastasia")
VOICE_NAME = os.getenv("VOICE_NAME", "id-ID-GadisNeural")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

# Logging Configuration
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("HermesJarvis")

# System Prompt
SYSTEM_PROMPT = """
You are Hermes, an autonomous Jarvis-class personal AI companion and engineering partner for Ahmad Yardan Rasika (ardans-dev), a brilliant software engineering student specializing in backend systems, distributed cloud architecture, and artificial intelligence.
Tone & Personality:
- Professional, articulate, sharp, loyal, and technically elite (like Friday/Jarvis).
- Primary languages: Bahasa Indonesia (fluent, modern, respectful, yet friendly) and English for code/technical terminology.
- When analyzing code or architecture, be precise, concise, identify root causes instantly, and provide elegant solutions.
- Address Ardan respectfully as "Dan", "Ardan", atau "Tuan Ardan" saat kontekstual.
- If asked about your identity or hosting: You run 24/7 on Microsoft Azure (East Asia, Hong Kong) on an Ubuntu node.
"""

# Global User Settings
USER_SETTINGS = {
    "voice_mode": "smart",  # "smart" (voice on voice), "always", "off"
}


def is_authorized(user_id: int) -> bool:
    """Check if sender matches owner ID."""
    if not OWNER_TELEGRAM_ID:
        return True
    return str(user_id).strip() == str(OWNER_TELEGRAM_ID).strip()


def sanitize_text_for_speech(text: str) -> str:
    """Remove markdown syntax, URLs, and code blocks for natural speech."""
    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " [Potongan kode saya sertakan di teks] ", text)
    # Remove inline code
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # Remove markdown headers and bold/italic asterisks
    cleaned = re.sub(r"[#*_~`]", "", cleaned)
    # Remove URLs
    cleaned = re.sub(r"https?://\S+", " tautan terlampir ", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:1000]  # Limit speech to first 1000 chars for snappy responses


def convert_audio_to_wav(input_path: str, output_path: str) -> bool:
    """Convert input audio (ogg/oga) to 16kHz 16-bit mono WAV for Azure Speech."""
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
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"FFmpeg conversion error: {e}")
        return False


def speech_to_text(audio_wav_path: str) -> str:
    """Transcribe WAV audio using Azure AI Speech STT."""
    if not speechsdk or not AZURE_SPEECH_KEY:
        logger.warning("Azure Speech SDK not configured or key missing.")
        return ""

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION
        )
        speech_config.speech_recognition_language = "id-ID"

        audio_config = speechsdk.audio.AudioConfig(filename=audio_wav_path)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )

        result = recognizer.recognize_once_async().get()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.info("Speech could not be recognized.")
            return ""
        else:
            logger.error(f"Speech recognition error: {result.cancellation_details.reason}")
            return ""
    except Exception as e:
        logger.error(f"STT Error: {e}")
        return ""


def text_to_speech(text: str, output_ogg_path: str) -> bool:
    """Synthesize text into speech using Azure Neural Voice."""
    if not speechsdk or not AZURE_SPEECH_KEY:
        return False

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION
        )
        speech_config.speech_synthesis_voice_name = VOICE_NAME
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            mp3_path = tmp_mp3.name

        audio_config = speechsdk.audio.AudioOutputConfig(filename=mp3_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        speak_text = sanitize_text_for_speech(text)
        if not speak_text:
            speak_text = "Baik Dan, respons lengkap telah saya tampilkan di pesan teks."

        result = synthesizer.speak_text_async(speak_text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Convert MP3 to OGG Opus for native Telegram voice bubble
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
            return os.path.exists(output_ogg_path)
        return False
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return False


def call_openrouter(messages: list) -> str:
    """Query OpenRouter LLM."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://gentle-river-0f3a40500.3.azurestaticapps.net",
        "X-Title": "Hermes-Jarvis-Telegram",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1500,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=40,
        )
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            logger.error(f"OpenRouter Error {response.status_code}: {response.text}")
            return f"⚠️ OpenRouter Gateway Error ({response.status_code}). Silakan coba sesaat lagi."
    except Exception as e:
        logger.error(f"Network error with OpenRouter: {e}")
        return f"⚠️ Gangguan koneksi ke AI Gateway: {e}"


# Command Handlers
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Access Denied. Hermes Jarvis is locked to authorized operator.")
        return

    welcome_msg = (
        "⚡ <b>HERMES JARVIS ONLINE [v3.0.0-Azure]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Halo Dan! Sistem Jarvis pribadi kamu sudah aktif dan siap beroperasi.\n\n"
        "🎙️ <b>Kemampuan Suara (Voice-to-Voice):</b>\n"
        "Kirimkan Voice Note kapan saja. Saya akan mendengarkan dan membalas balik dengan suara berbahasa Indonesia natural (Gadis Neural).\n\n"
        "👁️ <b>Kemampuan Penglihatan (Computer Vision):</b>\n"
        "Kirim foto codingan, screenshot error terminal, atau slide materi kuliah. Saya akan membedah dan memberikan solusinya.\n\n"
        "🛠️ <b>Perintah Operasional:</b>\n"
        "• <code>/status</code> - Cek telemetri live node Azure VM\n"
        "• <code>/voice [on|off|smart]</code> - Atur preferensi balasan suara\n"
        "• <code>/help</code> - Panduan lengkap fitur Jarvis\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>'Standing by for your command, Dan.'</i>"
    )
    await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command (Live Cloud Telemetry)."""
    if not is_authorized(update.effective_user.id):
        return

    # CPU & RAM Metrics
    cpu_pct = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    # Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    # Speech Service Status
    speech_status = "ONLINE (F0 Active)" if (speechsdk and AZURE_SPEECH_KEY) else "STANDBY"

    status_msg = (
        "📡 <b>AZURE CLOUD TELEMETRY: vm-hermes</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Region:</b> East Asia (Hong Kong)\n"
        f"⚡ <b>Compute:</b> Standard_B2ats_v2 (AMD EPYC)\n"
        f"⏱ <b>Uptime:</b> {hours}j {minutes}m {seconds}d\n\n"
        f"📊 <b>CPU Load:</b> {cpu_pct}%\n"
        f"🧠 <b>Physical RAM:</b> {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
        f"💾 <b>Swap Partition:</b> {swap.percent}% ({swap.used // (1024**2)}MB / {swap.total // (1024**2)}MB)\n"
        f"📁 <b>Disk Usage:</b> {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)\n"
        f"🎙️ <b>Neural Speech Engine:</b> {speech_status}\n"
        f"🔊 <b>Voice Mode:</b> {USER_SETTINGS['voice_mode'].upper()}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Semua sub-sistem beroperasi normal tanpa beban biaya ($0).</i>"
    )
    await update.message.reply_text(status_msg, parse_mode=ParseMode.HTML)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /voice settings."""
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


# Message Handlers
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming Voice Notes from Ardan."""
    if not is_authorized(update.effective_user.id):
        return

    voice = update.message.voice
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # 1. Download voice note
    with tempfile.TemporaryDirectory() as tmpdir:
        oga_path = os.path.join(tmpdir, "incoming.oga")
        wav_path = os.path.join(tmpdir, "incoming.wav")
        response_ogg_path = os.path.join(tmpdir, "response.ogg")

        voice_file = await context.bot.get_file(voice.file_id)
        await voice_file.download_to_drive(oga_path)

        # 2. Convert to WAV
        if not convert_audio_to_wav(oga_path, wav_path):
            await update.message.reply_text("⚠️ Gagal mengonversi audio suara.")
            return

        # 3. Transcribe via Azure STT
        transcription = speech_to_text(wav_path)
        if not transcription:
            await update.message.reply_text(
                "🎙️ Maaf Dan, suara kurang terdengar jelas atau Azure Speech Key belum disetel. Coba kirim ulang ya!"
            )
            return

        # Inform user what was heard
        status_msg = await update.message.reply_text(
            f"<i>🎙️ Mendengar: \"{transcription}\"</i>\n⏳ <i>Memproses...</i>",
            parse_mode=ParseMode.HTML,
        )

        # 4. Query LLM Brain
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcription},
        ]
        ai_response = call_openrouter(messages)

        # 5. Determine Voice Reply
        should_voice = USER_SETTINGS["voice_mode"] in ["smart", "always"]
        has_tts = False

        if should_voice and speechsdk and AZURE_SPEECH_KEY:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
            has_tts = text_to_speech(ai_response, response_ogg_path)

        # Update or delete status message
        await status_msg.delete()

        # Send Voice Note first if generated
        if has_tts and os.path.exists(response_ogg_path):
            with open(response_ogg_path, "rb") as f:
                await context.bot.send_voice(
                    chat_id=chat_id,
                    voice=f,
                    caption="🎙️ <i>Hermes Voice Response (Gadis Neural)</i>",
                    parse_mode=ParseMode.HTML,
                )

        # Send full formatted text
        await update.message.reply_text(ai_response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming photos/images for Computer Vision."""
    if not is_authorized(update.effective_user.id):
        return

    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]  # Highest resolution
    caption = update.message.caption or "Tolong analisis gambar/kode/arsitektur ini secara mendalam dan berikan penjelasan atau solusi teknis."

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text("👁️ <i>Memindai gambar dan membedah visual dengan Vision Engine...</i>", parse_mode=ParseMode.HTML)

    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "photo.jpg")
        photo_file = await context.bot.get_file(photo.file_id)
        await photo_file.download_to_drive(img_path)

        # Base64 Encode
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
        await status_msg.delete()

        # Check if voice response requested
        if USER_SETTINGS["voice_mode"] == "always" and speechsdk and AZURE_SPEECH_KEY:
            resp_ogg = os.path.join(tmpdir, "resp.ogg")
            if text_to_speech(ai_response, resp_ogg):
                with open(resp_ogg, "rb") as vf:
                    await context.bot.send_voice(chat_id=chat_id, voice=vf)

        await update.message.reply_text(ai_response)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process text chat."""
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

    # Check if voice mode is set to "always"
    if USER_SETTINGS["voice_mode"] == "always" and speechsdk and AZURE_SPEECH_KEY:
        with tempfile.TemporaryDirectory() as tmpdir:
            resp_ogg = os.path.join(tmpdir, "resp.ogg")
            if text_to_speech(ai_response, resp_ogg):
                with open(resp_ogg, "rb") as vf:
                    await context.bot.send_voice(chat_id=chat_id, voice=vf)

    await update.message.reply_text(ai_response)


def main():
    """Boot Hermes Jarvis Telegram Bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment!")
        sys.exit(1)

    logger.info("Initializing Hermes Jarvis Bot Application...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("voice", cmd_voice))

    # Multimodal Listeners
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("⚡ Hermes Jarvis Multimodal Engine Online. Starting Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
