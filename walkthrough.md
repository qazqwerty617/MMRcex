# Walkthrough: Spread, Blacklist, and App Links

I have implemented the requested features to enhance the bot's functionality and user experience.

## Changes

### 1. Spread Threshold (8%)

- **Config**: Confirmed `min_threshold` is set to `8.0%` in `config.yaml`.
- **Logic**: Updated `spread_detector.py` to:
  - Add a quality score bonus for spreads >= 8%.
  - Lower the quality threshold from 30 to 20 to ensure 8% spreads are not filtered out even with lower volume.

### 2. Blacklist Command

- **Command**: Added `/blacklist <SYMBOL>` command (e.g., `/blacklist BTC/USDT`).
- **Storage**: Blacklisted tokens are stored in `blacklist.json`.
- **Logic**:
  - The bot now polls for Telegram updates in its main loop.
  - Incoming `/blacklist` commands add the token to the list and save it.
  - The scanner filters out any opportunities for tokens in the blacklist.

### 3. App Link Button

- **Feature**: Added an "Open App / Trade" button to every alert.
- **Implementation**:
  - Uses an Inline Keyboard with a link to `https://www.mexc.com/exchange/{symbol}_USDT`.
  - This link typically triggers the MEXC app to open on mobile devices (Universal Links).

## Verification

### Manual Verification Steps

1. **Restart the Bot**:

    ```bash
    python bot_rest.py
    ```

2. **Test Blacklist**:
    - Send `/blacklist BTC/USDT` to the bot.
    - Verify the bot replies "Added BTC/USDT to blacklist."
    - Check `blacklist.json` to see the entry.
3. **Test Alerts**:
    - Wait for a spread alert.
    - Verify the alert contains the "Open App / Trade" button.
    - Click the button on your phone to verify it opens the MEXC app or trading page.

## Files Modified

- `config.yaml` (Verified)
- `bot_rest.py` (Added command processing and blacklist logic)
- `telegram_notifier.py` (Added button support and updates polling)
- `spread_detector.py` (Adjusted scoring for 8% spread)
- `blacklist.json` (Created)
