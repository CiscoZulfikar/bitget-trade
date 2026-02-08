# Bitget Futures Trading Bot

A Python-based trading bot for Bitget USDT-M Futures (Linear Swaps). It listens to Telegram channels for trade signals, parses them using Google Gemini AI, and executes orders via the Bitget V2 API.

## 🚀 Features

### Core Trading
- **Signal Parsing**: Listens to a target Telegram channel (via Userbot) for signals like `#BTC LONG` or `LIMIT SHORT ETH`.
- **AI-Powered**: Uses Gemini AI to intelligently parse unstructured text into structured trade data (Symbol, Entry, SL, Direction).
- **Execution**: Supports **Market** and **Limit** orders with Stop Loss.
- **Risk Management**: Auto-calculates position size based on SL distance, account balance, and risk percentage.

### Advanced Features
- **Concurrent Trade Limit**: Restricts maximum open trades to **3** (configurable) to prevent over-exposure.
- **Real-time Sync**: Tracks actual open positions on Bitget (including manual trades) for accurate status reporting.
- **Periodic Updates**: Sends a system status report (Equity, Balance, Open Trades) to the admin at **xx:00** and **xx:30**.
- **Commands**:
  - `HELP`: Show available commands.
  - `STATUS`: Show Equity, Available Balance, and Open Trade Count.
  - `TRADES`: List all open positions with PnL, ROI, Leverage, and Liquidation Price.

### Deployment & Monitoring
- **GCP Ready**: Optimized for Google Cloud Free Tier (`e2-micro`) with Swap Space support.
- **Resilient**:
  - **Auto-Reconnect**: Includes `monitor_bot.ps1` to keep SSH log streams alive.
  - **Graceful Shutdown**: Notifies via Telegram before stopping/restarting (`SIGTERM` handling).
  - **Startup Report**: Sends status and last channel message on boot.

## 🛠️ Setup

1.  **Environment Variables**:
    Create a `.env` file (do NOT commit this):
    ```env
    # Telegram
    API_ID=your_api_id
    API_HASH=your_api_hash
    CHANNEL_ID=target_channel_id
    NOTIFICATION_USER_ID=your_user_id
    BOT_TOKEN=your_bot_token
    
    # Bitget API
    BITGET_API_KEY=...
    BITGET_SECRET_KEY=...
    BITGET_PASSPHRASE=...
    
    # AI Model
    GOOGLE_API_KEY=...
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run Locally**:
    ```bash
    python main.py
    ```

## ☁️ Deployment (Google Cloud)

See [DEPLOY_GCP.md](DEPLOY_GCP.md) for a comprehensive guide on deploying to a free `e2-micro` instance.

**Quick Commands (Server)**:
- **Restart Bot**: `sudo systemctl restart tradingbot`
- **View Logs**: `sudo journalctl -u tradingbot -f`

**Monitoring (Local)**:
- Run `./monitor_bot.ps1` to auto-reconnect and stream logs from your desktop.

## 🧪 Testing

- **Mock Signals**: Send a DM to the bot:
  `LONG BTC ENTRY 95000 SL 94000`
- **Simulation Tool**:
  `python inject_signal.py "SHORT ETH ENTRY 2500 SL 2600"`
  *(Simulates logic without placing orders)*

## License
MIT