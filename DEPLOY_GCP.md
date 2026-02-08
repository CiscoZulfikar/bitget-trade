# Deploying to Google Cloud Platform (Free Tier)

This guide shows you how to deploy the Bitget Trading Bot to a **completely free** Google Cloud `e2-micro` instance.

## 1. Create the VM Instance

1.  Go to [Google Cloud Console](https://console.cloud.google.com/compute/instances).
2.  Click **Create Instance**.
3.  **Name**: `bitget-bot` (or similar).
4.  **Region**: Choose `us-west1`, `us-central1`, or `us-east1` (these typically have Free Tier availability).
5.  **Zone**: Any.
6.  **Machine Configuration**:
    *   Series: `E2`
    *   Machine type: `e2-micro` (2 vCPU, 1 GB memory) - **Wait for the "Micro instance is free..." badge to appear.**
7.  **Boot Disk**:
    *   Click "Change".
    *   OS: **Ubuntu** (recommended) or Debian.
    *   Version: Ubuntu 22.04 LTS (x86/64).
    *   Size: **30 GB** (Standard Persistent Disk). *Note: Up to 30GB is free.*
    *   *Note: GCP "Always Free Tier" includes 30GB Standard PD. Choose Standard Persistent Disk, not Balanced.*
8.  **Firewall**:
    *   Allow HTTP/HTTPS traffic (optional, but good for updates).
9.  Click **Create**.

## 2. Connect via SSH

1.  Once the instance is running, click the **SSH** button next to it in the console listing.
2.  A browser window will open a terminal session.

## 3. Clone & Setup

Run the following commands in the SSH terminal:

### A. Clone the Repository

Since your repository is **Public**, you can clone it directly:

```bash
# Install Git
sudo apt-get update && sudo apt-get install -y git

# Clone
git clone https://github.com/CiscoZulfikar/bitget-trade.git
cd bitget-trade
```

### B. Upload Credentials
Since `.env` is gitignored for security (and contains your private keys), it is **not** included in the repo clone. You must create it manually on the server.

1.  Use `nano` (or any other editor) to create the file. If `nano` is missing:
    ```bash
    sudo apt-get update && sudo apt-get install -y nano
    ```
2.  Run `nano .env` inside the `bitget-trade` directory on the server.
3.  Open your **local** `.env` file on your computer, select all text, and copy it.
4.  Paste it into the terminal window (Right-click or Ctrl+Shift+V usually works).
5.  Press `Ctrl+O`, `Enter` to save, then `Ctrl+X` to exit.

### C. Run the Setup Script
This script installs everything (Python, dependencies) and creates a "Swap File" to prevent the server from crashing due to low RAM.

```bash
chmod +x setup_gcp.sh
./setup_gcp.sh
```

## 4. Run the Bot

The setup script creates a system service named `tradingbot`.

*   **Start**: `sudo systemctl start tradingbot`
*   **Stop**: `sudo systemctl stop tradingbot`
*   **Restart**: `sudo systemctl restart tradingbot`
*   **Check Status**: `sudo systemctl status tradingbot`
*   **View Live Logs**: `sudo journalctl -u tradingbot -f`

## Troubleshooting

*   **Server hangs during start**: If the bot crashes, verify swap is active: `free -h` (Swap should > 0). The `setup_gcp.sh` script handles this automatically.
