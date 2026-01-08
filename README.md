# MEXC Futures Arbitrage Bot

Multi-exchange futures arbitrage monitoring bot with funding rate filter.

## Features

- 7 exchanges: MEXC, Binance, Bybit, Gate.io, KuCoin, OKX, BingX
- Funding rate filter (<0.5%)
- Volume filter ($500K+)
- Smart cooldown system
- Telegram topic support

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.yaml`:

- Add your Telegram bot token
- Set chat_id and message_thread_id for topic
- Adjust spread/volume thresholds

## Running

```bash
python bot_rest.py
```

## Deployment

Use `screen` to run in background:

```bash
screen -S mexc_bot
python bot_rest.py
# Ctrl+A, D to detach
```
