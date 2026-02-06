# Bitget Futures Trading Bot

A Python-based trading bot for Bitget USDT-M Futures (Linear Swaps).

## Features

- **Telegram Signal Parsing**: Listens to a Telegram channel (via Userbot) for trade signals (e.g., `#BTC LONG`).
- **AI-Powered Parsing**: Uses Gemini AI to parse unstructured signal text into structured JSON data.
- **Risk Management**:
  - Auto-calculates position size based on SL distance and account balance.
  - Defaults to a fixed risk percentage (configurable).
- **Execution**:
  - Uses `ccxt` to interact with Bitget V2 API.
  - Supports Market Orders with SL/TP.
  - **Mock Mode**: Can simulate trades offline or when network is restricted (uses Mock Price/Balance).
- **Notifications**: Sends real-time status updates (Entry, SL, PnL) to a private Telegram DM.

## Setup

1.  **Environment Variables**:
    Create a `.env` file with:
    ```env
    API_ID=your_telegram_api_id
    API_HASH=your_telegram_api_hash
    CHANNEL_ID=target_channel_id
    NOTIFICATION_USER_ID=your_user_id_for_dms
    BOT_TOKEN=your_bot_token
    
    BITGET_API_KEY=...
    BITGET_SECRET_KEY=...
    BITGET_PASSPHRASE=...
    
    # AI Model
    GOOGLE_API_KEY=...
    ```

2.  **Install Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```

3.  **Run**:
    ```bash
    python main.py
    ```

## Usage

- **Real Mode**: Places actual orders on Bitget if API keys are valid and network is open.
- **Mock Mode**:
  - DMs to the bot are treated as Mock Signals.
  - If Bitget API is unreachable, it falls back to Mock Price/Balance for testing logic.