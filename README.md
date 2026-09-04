# ⚡ Hermes Jarvis — Multimodal AI Assistant on Microsoft Azure

<div align="center">

  ![Azure](https://img.shields.io/badge/Hosted_on-Microsoft_Azure_East_Asia-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)
  ![Telegram](https://img.shields.io/badge/Interface-Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
  ![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
  ![Status](https://img.shields.io/badge/Daemon_Status-PM2_Online_24/7-22C55E?style=for-the-badge&logo=pm2&logoColor=white)

  <p align="center">
    <b>An autonomous, multimodal Jarvis-class AI companion engineered for high resilience, neural speech synthesis, and real-time computer vision.</b>
  </p>

</div>

---

## 🌌 Overview

**Hermes Jarvis** is an AI agent running 24/7 on an Azure Linux VM (`Standard_B2ats_v2`, East Asia). It elevates standard chat interactions into a seamless **Voice-to-Voice** and **Vision-enabled** engineering assistant.

### 🧬 Core Capabilities

1. 🎙️ **Voice-to-Voice (Speech Recognition & Neural TTS)**:
   - Powered by **Azure AI Speech Services (Free F0)**.
   - Transcribes incoming Telegram Voice Notes (`.oga` / Opus) with high precision in Bahasa Indonesia and English.
   - Generates articulate, natural Indonesian speech using **`id-ID-GadisNeural`**.
   - Sends replies as native playable Telegram Voice Notes with audio waveform.

2. 👁️ **Computer Vision & Multimodal Reasoning**:
   - Analyzes code on monitor screens, terminal stack traces, system architecture diagrams, and handwritten notes.
   - Powered by OpenRouter multimodal LLMs (`google/gemini-2.0-flash-exp:free`).

3. 📡 **Live Infrastructure Telemetry**:
   - Command `/status` monitors CPU usage, physical RAM, swap partition, disk storage, and node uptime in real-time.

4. 🛡️ **Whitelisted Security**:
   - Cryptographically checks Telegram User IDs to prevent unauthorized compute usage.

---

## 🚀 Quick Deployment (Azure VM)

```bash
# 1. Clone the repository
git clone https://github.com/ardans-dev/hermes-jarvis.git
cd hermes-jarvis

# 2. Configure Environment Variables
cp .env.example .env
nano .env

# 3. Run Automated Installer
chmod +x setup.sh
./setup.sh
```

---

## ⌨️ Command Reference

| Command | Description |
| :--- | :--- |
| `/start` | Displays system status and multimodal feature guide. |
| `/status` | Real-time telemetry report for the Azure VM node. |
| `/voice [smart\|on\|off]` | Configures speech response behavior. |
| `/help` | Detailed command documentation. |

---

## 🏛️ Architecture

```
User (Telegram) ──[ Voice Note / Photo / Text ]──> Telegram Bot API
                                                         │
                                                         ▼
                                                Azure VM (vm-hermes)
                                              ┌───────────────────────┐
                                              │   Hermes Jarvis Bot   │
                                              │   (PM2 Daemon 24/7)   │
                                              └──────────┬────────────┘
                                                         │
                      ┌──────────────────────────────────┴──────────────────────────────────┐
                      ▼                                                                     ▼
     [ Voice Note Processing ]                                              [ Vision / Text Reasoning ]
      • FFmpeg Audio Conversion                                              • Base64 Image Packaging
      • Azure Speech STT (id-ID)                                             • OpenRouter Multimodal LLM
      • Azure Neural TTS (Gadis)                                             • Architectural Analysis
                      │                                                                     │
                      └──────────────────────────────────┬──────────────────────────────────┘
                                                         │
                                                         ▼
User (Telegram) <──────[ Voice Waveform + Formatted Solution Text ]──────
```

---

<div align="center">
  <sub>Engineered with precision by <a href="https://github.com/ardans-dev">Ahmad Yardan Rasika (ardans-dev)</a>. Hosted on Microsoft Azure.</sub>
</div>
