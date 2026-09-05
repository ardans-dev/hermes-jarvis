# Hermes Jarvis - Multimodal Autonomous AI Assistant

An autonomous, multimodal Jarvis-class personal AI companion running 24/7 on Microsoft Azure Cloud. Engineered with natural Voice-to-Voice neural speech, real-time computer vision, task scheduling, cognitive memory, web search, and cloud telemetry.

[![Telegram Bot](https://img.shields.io/badge/Telegram_Bot-@ardans__ai__bot-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://t.me/ardans_ai_bot)
[![Cloud Host](https://img.shields.io/badge/Hosted_on-Microsoft_Azure_East_Asia-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)](https://gentle-river-0f3a40500.3.azurestaticapps.net)
[![Neural Voice](https://img.shields.io/badge/Neural_Voice-id--ID--GadisNeural-8B5CF6?style=flat-square&logo=azuredevops&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/ai-speech)
[![Daemon Status](https://img.shields.io/badge/Daemon_Status-PM2_Online_24/7-22C55E?style=flat-square&logo=pm2&logoColor=white)](https://pm2.keymetrics.io/)
[![License](https://img.shields.io/badge/License-MIT-emerald?style=flat-square)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [System Capabilities](#system-capabilities)
  - [1. Voice-to-Voice Neural Speech Pipeline](#1-voice-to-voice-neural-speech-pipeline)
  - [2. Multimodal Computer Vision](#2-multimodal-computer-vision)
  - [3. Persistent Cognitive Memory](#3-persistent-cognitive-memory)
  - [4. Task Scheduler & Audio Reminders](#4-task-scheduler--audio-reminders)
  - [5. Live Web Search & Operational Briefings](#5-live-web-search--operational-briefings)
  - [6. Remote Terminal & Cloud Diagnostics](#6-remote-terminal--cloud-diagnostics)
- [Telegram Command Reference](#telegram-command-reference)
- [System Architecture](#system-architecture)
- [Infrastructure & Tech Stack](#infrastructure--tech-stack)
- [Deployment Guide](#deployment-guide)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Installation & Service Setup](#installation--service-setup)
- [Process Supervision with PM2](#process-supervision-with-pm2)
- [Author & Credits](#author--credits)

---

## Overview

Hermes Jarvis is an autonomous personal AI assistant continuously deployed on an Azure Linux VM (`Standard_B2ats_v2`, East Asia, Hong Kong). It integrates multimodal language models, speech recognition, neural voice synthesis, and remote server telemetry into an always-on engineering assistant accessible via Telegram.

Engineered by Ahmad Yardan Rasika ([@ardans-dev](https://github.com/ardans-dev)), the system enables low-latency voice interaction, diagram and bug image analysis, memory persistence across conversation turns, and remote server monitoring.

---

## System Capabilities

### 1. Voice-to-Voice Neural Speech Pipeline
- **Speech-to-Text (STT)**: Decodes Telegram voice notes and audio clips into text via Microsoft Azure Speech Recognition REST API (Bahasa Indonesia `id-ID` and English `en-US`), with automated FFmpeg pre-conversion into 16kHz mono PCM WAV.
- **Text-to-Speech (TTS)**: Synthesizes high-fidelity Indonesian speech using Azure Neural Voice (`id-ID-GadisNeural`) converted to OGG/Opus voice notes.
- **Dynamic Voice Modes**:
  - `Smart Mode` (default): Replies with voice notes only when spoken to with an audio note, replying with text when messaged via text.
  - `Always Mode`: Responds with both an audio voice note and formatted markdown text.
  - `Silent Mode`: Suppresses voice synthesis and responds strictly with formatted text.

### 2. Multimodal Computer Vision
- Ingests image attachments, terminal error screenshots, circuit diagrams, and slides.
- Encodes media to Base64 data payloads and streams them to multimodal vision LLMs.
- Performs root-cause analysis (RCA), syntax error detection, and automated architectural code generation.

### 3. Persistent Cognitive Memory
- Local SQLite database engine (`hermes.db`) preserving conversation context across restarts.
- Tracks user history, preferences, and session context to eliminate repetitive user prompting.

### 4. Task Scheduler & Audio Reminders
- Built-in asynchronous task scheduler allowing users to set reminders via natural language or direct commands (`/remind`).
- Automatically fires alerts at scheduled times, synthesizing custom audio notifications.

### 5. Live Web Search & Operational Briefings
- Integrated zero-cost search backends (DuckDuckGo and Wikipedia API) for real-time information retrieval.
- Daily briefing generator (`/briefing`) summarizing tasks, weather, and schedule updates into an executive audio digest.

### 6. Remote Terminal & Cloud Diagnostics
- Secure cloud command runner (`/exec`, `/whoami`) guarded by Telegram administrator ID verification.
- Non-blocking real-time hardware diagnostics (`/status`) reporting CPU utilization, memory allocations, disk capacity, and uptime directly from the host Azure VM.

---

## Telegram Command Reference

| Command | Parameter | Functionality |
|---|---|---|
| `/status` | None | Displays live Azure VM metrics: CPU %, RAM, Swap, Disk, and Node Uptime |
| `/voice` | `smart` | Sets voice mode to smart replies (voice replies to voice notes, text to text) |
| `/voice` | `on` | Sets voice mode to always synthesize an audio note alongside text |
| `/voice` | `off` | Enforces silent mode (text responses only) |
| `/remind` | `<time> <text>` | Schedules a proactive reminder with optional audio notification |
| `/reminders` | None | Lists active scheduled reminders and allows cancellation |
| `/briefing` | None | Triggers an instant audio morning/operational briefing |
| `/exec` | `<cmd>` | Executes authorized administrative commands on the Azure VM |
| `/clear` | None | Clears recent conversation memory buffer |
| `/start` | None | Initializes session and displays system overview |
| `/help` | None | Lists complete operational documentation and commands |

---

## System Architecture

```text
User Device (Telegram Client: @ardans_ai_bot)
      │
      ├───> Voice Note (.oga) ──> FFmpeg Conversion (16kHz WAV) ──> Azure Speech STT (id-ID) ───┐
      ├───> Image / Screenshot ─> Base64 Encoding & Payload ──────> Multimodal Vision Engine ──┤
      └───> Text Query ───────────────────────────────────────────> OpenRouter Gateway ─────────┤
                                                                                                │
                                                                                                ▼
                                                                                   ┌────────────────────────┐
                                                                                   │   Hermes Jarvis Core   │
                                                                                   │  (Azure VM 24/7 PM2)   │
                                                                                   │  - SQLite Memory       │
                                                                                   │  - Task Scheduler      │
                                                                                   │  - Telemetry Monitor   │
                                                                                   └───────────┬────────────┘
                                                                                               │
                            ┌──────────────────────────────────────────────────────────────────┴────────────┐
                            ▼                                                                               ▼
                  [TTS Neural Engine]                                                             [Text Solution]
                   - SSML Generator                                                                - Markdown formatting
                   - Azure Voice (GadisNeural)                                                     - Code blocks & RCA
                   - FFmpeg Opus Encoder                                                           - Execution outputs
                            │                                                                               │
                            └───────────────────────────────┬───────────────────────────────────────────────┘
                                                            ▼
                                    Telegram Bot dispatches Voice Note & Text
```

---

## Infrastructure & Tech Stack

| Layer | Component | Specification / Version |
|---|---|---|
| Host Platform | Microsoft Azure VM | `Standard_B2ats_v2` (AMD EPYC, 2 vCPUs, Ubuntu 24.04 LTS) |
| Voice Recognition | Azure Speech Services | Tier F0 / Direct REST API (`id-ID`, `en-US`) |
| Neural Speech | Azure Neural TTS | Voice: `id-ID-GadisNeural` (REST API SSML) |
| LLM Gateway | OpenRouter API | Multimodal LLMs (`openrouter/free`, `google/gemma-2-9b-it:free`) |
| Bot Framework | python-telegram-bot | Version 20+ (Asyncio architecture) |
| Process Supervisor | PM2 Runtime | Daemon management with automatic failure recovery |
| Audio Utilities | FFmpeg / pydub | Conversion between OGG/Opus and 16kHz PCM WAV |
| Hardware Telemetry | psutil | System metrics extraction (CPU, Memory, Disk) |
| Local Storage | SQLite3 | Persistent state, conversation history, and reminder records |

---

## Deployment Guide

### Prerequisites
- Linux host running Ubuntu 22.04 LTS or 24.04 LTS
- Python 3.10+ installed
- FFmpeg installed (`sudo apt update && sudo apt install -y ffmpeg`)
- Node.js & PM2 installed (`sudo apt install -y nodejs npm && sudo npm install -g pm2`)

### Environment Configuration
Clone the repository and create the configuration file:

```bash
git clone https://github.com/ardans-dev/hermes-jarvis.git
cd hermes-jarvis
cp .env.example .env
```

Configure the environment keys inside `.env`:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
ADMIN_USER_ID="your_telegram_numeric_id"
OPENROUTER_API_KEY="your_openrouter_api_key"
OPENROUTER_MODEL="openrouter/free"
AZURE_SPEECH_KEY="your_azure_speech_key"
AZURE_SPEECH_REGION="eastasia"
VOICE_NAME="id-ID-GadisNeural"
```

### Installation & Service Setup
Run the automated installation script:

```bash
chmod +x setup.sh
./setup.sh
```

Alternatively, configure manually:

```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start via PM2
pm2 start bot.py --name "hermes-jarvis" --interpreter ./venv/bin/python3
pm2 save
pm2 startup
```

---

## Process Supervision with PM2

Check running status and live telemetry:

```bash
# View process status
pm2 status

# Stream realtime logs
pm2 logs hermes-jarvis

# Restart daemon
pm2 restart hermes-jarvis

# Stop daemon
pm2 stop hermes-jarvis
```

---

## Author & Credits

- **Developer**: Ahmad Yardan Rasika ([@ardans-dev](https://github.com/ardans-dev))
- **Live Agent**: Telegram [@ardans_ai_bot](https://t.me/ardans_ai_bot)
- **Developer Portfolio**: [gentle-river-0f3a40500.3.azurestaticapps.net](https://gentle-river-0f3a40500.3.azurestaticapps.net/)
