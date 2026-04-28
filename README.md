# G3Bot

A lightweight OpenRouter chat client designed for vintage Macs — tested on an iMac G3 (1999) with Netscape Communicator 4.x under Mac OS 8.6.

The page itself uses no JavaScript and only basic HTML (tables, `<font>` tags) so it renders correctly in browsers from the late 1990s. A small Flask server running on your NAS handles all the modern stuff (HTTPS, JSON, API authentication).

## Architecture

```
iMac G3 (Netscape 4) ──HTTP──► NAS / OMV 7 (Docker) ──HTTPS──► OpenRouter API
```

## Setup

1. Get an API key from <https://openrouter.ai/>

2. On your NAS (OpenMediaVault 7), clone the repository:

   ```
   git clone https://github.com/ruhtrajer/G3Bot.git
   cd G3Bot
   ```

3. Create a `.env` file with your key:

   ```
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
   ```

4. Start the container:

   ```
   docker compose up -d
   ```

5. On the iMac G3, open Netscape and go to:

   ```
   http://<nas-ip>:3615/
   ```

## Features

- Free models only (auto-filtered from the OpenRouter catalogue)
- Dropdown: **Company — Model Name** with a description table
- Zero JavaScript — works with pure HTML form submissions
- Mac OS 8.6 Platinum visual style
- Model cache refreshes every hour (or on demand via the Refresh button)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `G3BOT_PORT` | `5000` | Internal Flask port |
| `G3BOT_CACHE_TTL` | `3600` | Model cache duration (seconds) |
