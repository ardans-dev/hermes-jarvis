# ⚡ Hermes Jarvis — Multimodal Autonomous AI Assistant

<div align="center">

  <a href="https://t.me/ardans_ai_bot" target="_blank">
    <img src="https://img.shields.io/badge/Telegram_Bot-@ardans__ai__bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Bot" />
  </a>
  <a href="https://gentle-river-0f3a40500.3.azurestaticapps.net" target="_blank">
    <img src="https://img.shields.io/badge/Hosted_on-Microsoft_Azure_East_Asia-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" alt="Azure" />
  </a>
  <img src="https://img.shields.io/badge/Neural_Voice-id--ID--GadisNeural-8B5CF6?style=for-the-badge&logo=azuredevops&logoColor=white" alt="Neural Voice" />
  <img src="https://img.shields.io/badge/Daemon_Status-PM2_Online_24/7-22C55E?style=for-the-badge&logo=pm2&logoColor=white" alt="Status" />

  <p align="center">
    <b>An autonomous, multimodal Jarvis-class personal AI companion running 24/7 on Microsoft Azure Cloud.<br />
    Engineered with natural Voice-to-Voice neural speech, real-time computer vision, and live system telemetry.</b>
  </p>

  <p align="center">
    👉 <b><a href="https://t.me/ardans_ai_bot">Chat with Hermes Jarvis on Telegram (@ardans_ai_bot)</a></b> 👈
  </p>

</div>

---

## 🌌 Overview

**Hermes Jarvis** is an autonomous AI assistant deployed 24/7 on an Azure Linux VM (`Standard_B2ats_v2`, East Asia, Hong Kong). It transforms everyday mobile communication into a full-fledged Iron Man-style engineering companion for **Ahmad Yardan Rasika ([@ardans-dev](https://github.com/ardans-dev))**.

### 🧬 Core Capabilities

1. 🎙️ **Voice-to-Voice (Azure Speech REST API)**:
   - **Speech-to-Text (STT)**: Listens to incoming Telegram Voice Notes and audio attachments in Bahasa Indonesia & English with automated FFmpeg conversion (16kHz PCM).
   - **Text-to-Speech (TTS)**: Synthesizes crystal-clear, expressive Indonesian speech using **Azure Neural Voice `id-ID-GadisNeural`**.
   - **Smart Voice Mode**: Intelligently responds with a Voice Note when spoken to, and text when typed to.

2. 👁️ **Computer Vision & Multimodal Reasoning**:
   - Takes photos and screenshots of code errors, terminal stack traces, server architectures, and lecture slides.
   - Identifies bug root causes instantly and proposes precise refactoring and bugfixes.

3. 📡 **Live Cloud Telemetry (`/status`)**:
   - Non-blocking real-time hardware diagnostics directly from the Azure VM: CPU load %, RAM/Swap allocation, disk usage, and node uptime.

4. 🌐 **Portfolio & Contact Relay**:
   - Integrated with Ardan's official portfolio: [`gentle-river-0f3a40500.3.azurestaticapps.net`](https://gentle-river-0f3a40500.3.azurestaticapps.net/).

---

## ⌨️ Telegram Command Reference

| Command | Action |
| :--- | :--- |
| `/status` | 📡 Inspect live CPU, RAM, Disk, and node uptime on Azure VM (`vm-hermes`) |
| `/voice smart` | 🎙️ Smart Mode: Reply with voice notes only when spoken to (Recommended) |
| `/voice on` | 🔊 Always Mode: Reply with both voice note and text for every prompt |
| `/voice off` | 🔇 Silent Mode: Reply exclusively with formatted text |
| `/start` | ⚡ Initialize conversation and view capabilities overview |
| `/help` | 📖 Display full command manual and operational guide |

---

## 🏛️ System Architecture

```
User (Telegram @ardans_ai_bot)
      │
      ├─► [Voice Note (.oga)] ──► FFmpeg (16kHz WAV) ──► Azure Speech STT (id-ID) ──┐
      ├─► [Screenshot / Photo] ─► Base64 Data URL ─────► Multimodal Vision Engine ──┤
      └─► [Text Query] ────────────────────────────────► OpenRouter Free Gateway ───┤
                                                                                    │
                                                                                    ▼
                                                                        ┌───────────────────────┐
                                                                        │   Hermes Jarvis Core  │
                                                                        │   (Azure VM 24/7 PM2) │
                                                                        └───────────┬───────────┘
                                                                                    │
               ┌────────────────────────────────────────────────────────────────────┴──────────┐
               ▼                                                                               ▼
     [TTS Synthesis Engine]                                                          [Solution Output]
      • Filter Code Blocks & URLs                                                     • Clean Markdown
      • Azure Neural Voice (Gadis)                                                    • Terminal Code Snippets
      • FFmpeg (Opus Waveform OGG)                                                    • Diagnostic RCA
               │                                                                               │
               └────────────────────────────────┬──────────────────────────────────────────────┘
                                                ▼
                              User receives Voice Note + Formatted Reply!
```

---

## 🚀 Quick Deployment Guide

```bash
# 1. Clone repository
git clone https://github.com/ardans-dev/hermes-jarvis.git
cd hermes-jarvis

# 2. Configure Environment (.env)
cat << 'EOF' > .env
TELEGRAM_BOT_TOKEN="your_bot_token"
OPENROUTER_API_KEY="your_openrouter_key"
OPENROUTER_MODEL="openrouter/free"
AZURE_SPEECH_KEY="your_azure_speech_key"
AZURE_SPEECH_REGION="eastasia"
VOICE_NAME="id-ID-GadisNeural"
EOF

# 3. Launch automated installer & PM2 daemon
chmod +x setup.sh
./setup.sh
```

---

## 🛡️ Tech Stack & Infrastructure

- **Cloud Compute**: Microsoft Azure VM (`Standard_B2ats_v2`, AMD EPYC, 2 vCPUs, Ubuntu 24.04 LTS)
- **Neural Speech**: Microsoft Azure Cognitive Services (Speech Tier F0, East Asia)
- **Voice Model**: `id-ID-GadisNeural`
- **LLM Gateway**: OpenRouter API (`openrouter/free`, `google/gemma-2-9b-it:free`, `meta-llama/llama-3.3-70b-instruct:free`)
- **Process Supervisor**: PM2 Daemon
- **Audio Processing**: FFmpeg (libopus, PCM s16le)
- **Zero-Cost Engineering**: $0.00 / month (100% free under Azure for Students & OpenRouter Free Tier)

---

<div align="center">
  <sub>Engineered with passion by <a href="https://github.com/ardans-dev">Ahmad Yardan Rasika (ardans-dev)</a>. Powered by Microsoft Azure.</sub>
</div>
