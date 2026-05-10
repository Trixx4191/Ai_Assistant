# 🤖 Personal AI Telegram Bot

A fully online, always-on personal AI assistant running on Telegram. Powered by Groq (LLaMA 4 + LLaMA 3.3), with image analysis, reverse image search, web search, conversation memory, and tone-matching built in.

---

## Features

| Feature | What it does |
|---|---|
| 💬 **Conversation memory** | Remembers the last 20 turns per chat — no need to repeat yourself |
| 🎭 **Tone matching** | Casual message → casual reply. Technical question → structured answer |
| 🔍 **Web search** | `/search` or just ask about current events — auto-routes to live search |
| 📷 **Image analysis** | Send any photo — it describes, identifies, reads text, finds people/objects |
| 🔄 **Reverse image search** | Google Lens → source search → AI fallback pipeline |
| 📄 **Document reading** | Send a PDF or text file and it'll summarize/analyze it |
| 🔒 **Access control** | Optional allowlist so only you can use the bot remotely |
| 🌐 **Webhook support** | Run on a server 24/7 with a single env variable |

---

## Quick Start

### 1. Clone / unzip the project

```
your-bot/
├── bot.py
├── config.py
├── requirements.txt
├── .env
└── ai/
    └── Model.py
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
| `ALLOWED_USER_IDS` | ⭕ | (open) | Comma-separated Telegram user IDs |
| `MEMORY_TURNS` | ⭕ | `20` | Conversation turns to remember |
| `WEBHOOK_URL` | ⭕ | — | Switch from polling to webhook mode |
| `WEBHOOK_PORT` | ⭕ | `8443` | Port for webhook server |
| `WEBHOOK_SECRET` | ⭕ | — | Optional webhook secret token |

---

## Deploying Online (Always On)

### Railway (easiest)
1. Push code to a GitHub repo
2. Connect repo to [railway.app](https://railway.app)
3. Add all env variables in the Railway dashboard
4. Set `WEBHOOK_URL` to the Railway-generated URL + `/bot`
5. Deploy — done

### Render
Same as Railway. Use the generated `.onrender.com` URL as your `WEBHOOK_URL`.

### VPS (DigitalOcean, Linode, etc.)
```bash
# Run in background with pm2
npm install -g pm2
pm2 start "python bot.py" --name mybot
pm2 save
```

---

## Tech Stack

- **Runtime**: Python 3.11+
- **Bot framework**: `python-telegram-bot` v21+
- **LLM**: Groq API
  - Text: `llama-3.3-70b-versatile`
  - Vision: `meta-llama/llama-4-scout-17b-16e-instruct`
  - Search: `compound-beta-mini`
- **Web search**: Tavily (primary) → Groq compound (fallback)
- **Reverse image search**: Google Lens → google_img_source_search → AI fallback

---

## Project Structure

```
├── bot.py          # Telegram handlers, routing, commands
├── config.py       # Env loading, all settings in one place
├── requirements.txt
├── .env            # Your secrets (never commit this)
└── ai/
    └── Model.py    # All AI logic: chat, vision, search, memory
```
