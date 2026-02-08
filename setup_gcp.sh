#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Bitget Trading Bot Setup for GCP (Free Tier)..."

# 1. SWAP SPACE CREATION (CRITICAL for e2-micro 1GB RAM)
if [ -f /swapfile ]; then
    echo "✅ Swap file already exists."
else
    echo "⚠️ Creating 2GB Swap File (Crucial for low RAM instances)..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ Swap created."
fi

# 2. SYSTEM UPDATES & DEPENDENCIES
echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git tmux htop nano

# 3. PROJECT SETUP
PROJECT_DIR="$HOME/bitget-trade"
VENV_DIR="$PROJECT_DIR/venv"

# Ensure we are in the right directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found at $PROJECT_DIR"
    echo "Please clone the repo to $HOME/bitget-trade first."
    exit 1
fi

cd "$PROJECT_DIR"

# 4. PYTHON ENVIRONMENT
echo "🐍 Setting up Python Virtual Environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# Install requirements
echo "📦 Installing Python libraries..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

# 5. SERVICE CONFIGURATION
echo "⚙️ Configuring Systemd Service..."

SERVICE_FILE="tradingbot.service"
SYSTEM_SERVICE_PATH="/etc/systemd/system/$SERVICE_FILE"

# Dynamically update the service file with the correct User and Path
# We assume the repo contains a template tradingbot.service
if [ -f "$SERVICE_FILE" ]; then
    # Create a temporary file with replaced values
    sed -e "s|User=.*|User=$USER|g" \
        -e "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" \
        -e "s|ExecStart=.*|ExecStart=$VENV_DIR/bin/python3 main.py|g" \
        "$SERVICE_FILE" > "tradingbot.service.tmp"

    # Install the service
    sudo mv "tradingbot.service.tmp" "$SYSTEM_SERVICE_PATH"
    
    # Reload systemd
    sudo systemctl daemon-reload
    sudo systemctl enable tradingbot
    
    echo "✅ Service installed and enabled."
else
    echo "❌ Warning: tradingbot.service template not found in project folder."
fi

echo "=================================================="
echo "🎉 Setup Complete!"
echo "To start the bot:"
echo "  1. Ensure .env file is created with your credentials."
echo "  2. Run: sudo systemctl start tradingbot"
echo "  3. Check status: sudo systemctl status tradingbot"
echo "  4. View logs: sudo journalctl -u tradingbot -f"
echo "=================================================="
