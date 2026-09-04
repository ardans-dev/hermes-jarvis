#!/bin/bash
set -e

echo "⚡ [HERMES JARVIS] Initiating Multimodal Engine Deployment on Azure VM..."

# 1. Check FFmpeg
echo "📦 [1/4] Checking and installing system audio libraries (ffmpeg)..."
if ! command -v ffmpeg &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq ffmpeg
    echo "✅ ffmpeg installed successfully."
else
    echo "✅ ffmpeg is already installed."
fi

# 2. Virtualenv
echo "🐍 [2/4] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ venv created."
fi

echo "📥 [3/4] Installing Python requirements (Azure Speech, PTB, etc.)..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo "✅ Dependencies installed."

# 3. Check .env
if [ ! -f ".env" ]; then
    echo "⚠️ .env file not found. Creating from template..."
    cp .env.example .env
    echo "❗ Please configure your credentials in .env before starting."
fi

# 4. Process restart
echo "🔄 [4/4] Starting/Restarting daemon with PM2..."
pm2 delete hermes-jarvis 2>/dev/null || true
pm2 delete bot 2>/dev/null || true
pkill -9 -f "bot.py" 2>/dev/null || true

pm2 start bot.py --name hermes-jarvis --interpreter ./venv/bin/python
pm2 save

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 HERMES JARVIS IS NOW ONLINE 24/7!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pm2 status
