# Deploying to Google Cloud Platform (Free Tier)

This guide shows you how to deploy the Bitget Trading Bot to a **completely free** Google Cloud `e2-micro` instance.

## 1. Create the VM Instance

1.  Go to [Google Cloud Console](https://console.cloud.google.com/compute/instances).
2.  Click **Create Instance**.
3.  **Name**: `bitget-bot` (or similar).
4.  **Region**: `us-west1` (Oregon) - *User specified*.
5.  **Zone**: `us-west1-b` - *User specified*.
6.  **Machine Configuration**:
    *   Series: `E2`
    *   Machine type: `e2-micro` (2 vCPU, 1 GB memory) - **Wait for the "Micro instance is free..." badge to appear.**
7.  **Boot Disk**:
    *   Click "Change".
    *   OS: **Ubuntu Minimal** (or Ubuntu).
    *   Version: **Ubuntu 24.04 LTS** (noble) - `ubuntu-minimal-2404-noble-amd64-v20260129`
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

## 5. Testing Logic (Simulation)

You can test the bot's logic **without placing real orders** using the `inject_signal.py` script. This is perfect for verifying your keys and the bot's decision making (Market vs Limit).

### How to use:
1.  Navigate to the project folder:
    ```bash
    cd ~/bitget-trade
    ```
2.  Run the injector (make sure to quote the message):
    ```bash
    ../bitget-trade/venv/bin/python3 inject_signal.py "LONG BTC ENTRY 98000 SL 97500"
    ```

### Examples:

**1. Market Entry Test** (If price is close to entry):
```bash
# Finds current price (e.g. 98000) -> Output: MARKET ACTION
../bitget-trade/venv/bin/python3 inject_signal.py "LONG BTC ENTRY 98000 SL 97000"
```

**2. Limit Entry Logic Test** (If price is 0.5% - 1.0% different):
```bash
# If current is 98000, and you say 97200 (0.8% diff) -> Output: LIMIT ACTION
../bitget-trade/venv/bin/python3 inject_signal.py "LONG BTC ENTRY 97200 SL 96000"
```

**3. Explicit Limit Override**:
```bash
# Forces LIMIT even if price is perfect
../bitget-trade/venv/bin/python3 inject_signal.py "LIMIT LONG BTC ENTRY 98000 SL 97000"
```

**4. Abort Test** (Price too far > 1%):
```bash
# If current is 98000, and you say 90000 -> Output: ABORT
../bitget-trade/venv/bin/python3 inject_signal.py "LONG BTC ENTRY 90000 SL 89000"
```

## Troubleshooting

*   **Server hangs during start**: If the bot crashes, verify swap is active: `free -h` (Swap should > 0). The `setup_gcp.sh` script handles this automatically.
