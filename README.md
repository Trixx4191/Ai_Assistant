<div align="center">

<img src="https://img.shields.io/badge/Personal%20AI-Telegram%20Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Personal AI Telegram Bot"/>

**Always-on personal AI assistant on Telegram — powered by LLaMA 4, with vision, web search, memory & more.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Powered%20by-Groq-F55036?style=flat-square)](https://groq.com)
[![Telegram](https://img.shields.io/badge/Bot%20Framework-python--telegram--bot%20v21-26A5E4?style=flat-square&logo=telegram)](https://python-telegram-bot.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Trixx4191/Ai_Assistant?style=flat-square&color=f59e0b)](https://github.com/Trixx4191/Ai_Assistant/releases)
[![Stars](https://img.shields.io/github/stars/Trixx4191/Ai_Assistant?style=flat-square&color=facc15)](https://github.com/Trixx4191/Ai_Assistant/stargazers)

[Features](#features) · [Quick Start](#quick-start) · [Commands](#commands) · [Environment Variables](#environment-variables) · [Deploying](#deploying-online-always-on) · [Tech Stack](#tech-stack)

</div>

---

## What is this?

A fully online, always-on personal AI assistant running on Telegram. Powered by Groq (LLaMA 4 + LLaMA 3.3), with image analysis, reverse image search, web search, conversation memory, and tone-matching built in.

No UI to maintain. No app to install. Just open Telegram and talk.

---

## Features

| Feature | What it does |
|---|---|
| 💬 **Conversation memory** | Remembers the last 20 turns per chat — no need to repeat yourself |
| 🎭 **Tone matching** | Casual message → casual reply. Technical question → structured answer |
| 🔍 **Web search** | `/search` or just ask about current events — auto-routes to live search |
| 📷 **Image analysis** | Send any photo — describes, identifies, reads text, finds people/objects |
| 🔄 **Reverse image search** | Google Lens → source search → AI fallback pipeline |
| 📄 **Document reading** | Send a PDF or text file and it'll summarize/analyze it |
| 🔒 **Access control** | Optional allowlist so only you (or chosen users) can use the bot |
| 🌐 **Webhook support** | Run on a server 24/7 with a single env variable |

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/Trixx4191/Ai_Assistant.git
cd Ai_Assistant
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
```

### 4. Run

```bash
python bot.py
```

---

## Getting Your API Keys

| Key | Where to get it | Cost |
|---|---|---|
| `BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) on Telegram | Free |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free tier available |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) | Free tier available |

---

## Commands

| Command | What it does |
|---|---|
| `/start` | Greeting + intro |
| `/help` | Show all commands |
| `/search <query>` | Search the web right now |
| `/image <query>` | Find image pages online |
| `/clear` | Wipe conversation memory and start fresh |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token from BotFather |
| `GROQ_API_KEY` | ✅ | — | Groq API key |
| `TAVILY_API_KEY` | ⭕ | — | Enables richer web search |
| `ALLOWED_USER_IDS` | ⭕ | (open) | Comma-separated Telegram user IDs for access control |
| `MEMORY_TURNS` | ⭕ | `20` | Conversation turns to remember |
| `WEBHOOK_URL` | ⭕ | — | Switch from polling to webhook mode |
| `WEBHOOK_PORT` | ⭕ | `8443` | Port for webhook server |
| `WEBHOOK_SECRET` | ⭕ | — | Optional webhook secret token |

---

## Project Structure

```
├── bot.py           # Telegram handlers, routing, commands
├── config.py        # Env loading, all settings in one place
├── requirements.txt
├── .env             # Your secrets (never commit this)
└── ai/
    └── Model.py     # All AI logic: chat, vision, search, memory
```

---

## Deploying Online (Always On)

### Railway (easiest)

1. Push this repo to GitHub
2. Connect to [railway.app](https://railway.app)
3. Add all env variables in the Railway dashboard
4. Set `WEBHOOK_URL` to the Railway-generated URL + `/bot`
5. Deploy — done

### Render

Same as Railway. Use the generated `.onrender.com` URL as your `WEBHOOK_URL`.

### VPS (DigitalOcean, Linode, Hetzner, etc.)

```bash
# Keep running in the background with pm2
npm install -g pm2
pm2 start "python bot.py" --name ai-assistant
pm2 save
pm2 startup
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+ |
| Bot framework | `python-telegram-bot` v21+ |
| LLM (text) | Groq — `llama-3.3-70b-versatile` |
| LLM (vision) | Groq — `meta-llama/llama-4-scout-17b-16e-instruct` |
| LLM (search) | Groq — `compound-beta-mini` |
| Web search | Tavily (primary) → Groq compound (fallback) |
| Reverse image search | Google Lens → google_img_source_search → AI fallback |

---

## Contributing

Pull requests are welcome! For major changes, open an issue first.

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

[MIT](LICENSE) © 2025 Trixx4191

---

<div align="center">
  <sub>If this saved you time, consider giving it a ⭐</sub>
</div>
