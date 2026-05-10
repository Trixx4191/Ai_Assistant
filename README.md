# 🤖 Personal AI Telegram Bot (v2)

A fully online, always-on personal AI assistant running on Telegram.
Powered by Groq (GPT-OSS 120B + LLaMA 3.3), with voice transcription,
image analysis, Perplexity-powered web search, conversation memory, and
deep cybersecurity skills built in.

---

## What's New in v2

| Change | Detail |
|---|---|
| 🎙 **Voice messages** | Send a voice note — Whisper Large v3 Turbo transcribes it, AI replies |
| 🧠 **Smarter vision** | GPT-OSS 120B replaces deprecated Llama 4 Maverick (Groq, Mar 2026) |
| 🌐 **Perplexity Sonar Pro** | Real-time cited web search replaces Tavily as primary |
| 🔐 **Cybersec commands** | `/cve`, `/exploit`, `/mitre`, `/hash` — specialist threat intel |
| ⚡ **Auto model routing** | Casual chat → LLaMA 3.1 8B; technical Q&A → LLaMA 3.3 70B; reasoning → GPT-OSS 120B |

---

## Features

| Feature | What it does |
|---|---|
| 💬 **Conversation memory** | Remembers the last 20 turns per chat |
| 🎭 **Tone matching** | Casual message → casual reply. Technical → structured |
| 🔍 **Web search** | `/search` or ask about current events — Perplexity Sonar Pro |
| 🎙 **Voice transcription** | Send voice notes → Whisper STT → AI reply |
| 📷 **Image analysis** | GPT-OSS 120B describes, identifies, reads text in photos |
| 🔄 **Reverse image search** | Google Lens → source search → AI fallback pipeline |
| 📄 **Document reading** | Send a PDF or text file and it'll summarise/analyse it |
| 🔐 **Cybersecurity depth** | CVE lookup, exploit search, MITRE ATT&CK, hash reputation |
| 🔒 **Access control** | Optional allowlist so only you can use the bot remotely |
| 🌐 **Webhook support** | Run on a server 24/7 with a single env variable |

---

## Quick Start

### 1. Clone / unzip the project

```
your-bot/
├── bot.py
├── cli.py
├── config.py
├── requirements.txt
├── .env
└── ai/
    └── Model.py
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up your `.env` file

```env
BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
PERPLEXITY_API_KEY=your_perplexity_api_key
```

### 4. Run

```bash
python bot.py
```

For terminal mode:

```bash
python cli.py
```

---

## Getting Your API Keys

| Key | Where to get it | Cost |
|---|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram | Free |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Free tier available |
| `PERPLEXITY_API_KEY` | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) | Free tier / $5 credits with Pro |

---

## Commands

| Command | What it does |
|---|---|
| `/start` | Greeting + intro |
| `/help` | Show all commands |
| `/search <query>` | Search the web (Perplexity Sonar Pro) |
| `/image <query>` | Find image pages online |
| `/cve <CVE-ID>` | Look up a CVE — CVSS, affected versions, mitigations |
| `/exploit <term>` | Find public exploits and PoCs |
| `/mitre <technique>` | Look up a MITRE ATT&CK technique |
| `/hash <hash>` | Check MD5/SHA256 hash reputation |
| `/clear` | Wipe conversation memory |

The CLI also supports:

| Command | What it does |
|---|---|
| `/vision <path> [prompt]` | Analyze an image from disk |
| `/read <path> [prompt]` | Read a PDF/text file and ask about it |
| `/transcribe <path>` | Transcribe a local audio file |
| `/models` | Show model routing |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram bot token |
| `GROQ_API_KEY` | ✅ | — | Groq API key (text, vision, Whisper) |
| `PERPLEXITY_API_KEY` | ⭕ | — | Primary web search (Sonar Pro) |
| `TAVILY_API_KEY` | ⭕ | — | Fallback web search if Perplexity not set |
| `ALLOWED_USER_IDS` | ⭕ | (open) | Comma-separated Telegram user IDs |
| `MEMORY_TURNS` | ⭕ | `20` | Conversation turns to remember |
| `WEBHOOK_URL` | ⭕ | — | Switch to webhook mode |
| `WEBHOOK_PORT` | ⭕ | `8443` | Port for webhook server |
| `WEBHOOK_SECRET` | ⭕ | — | Optional webhook secret token |

---

## Tech Stack

- **Runtime**: Python 3.11+
- **Bot framework**: `python-telegram-bot` v21+
- **LLM (casual/fast)**: Groq — `llama-3.1-8b-instant`
- **LLM (technical)**: Groq — `llama-3.3-70b-versatile`
- **LLM (vision/reasoning)**: Groq — `openai/gpt-oss-120b`
- **Speech-to-text**: Groq — `whisper-large-v3-turbo` (216x real-time)
- **Web search**: Perplexity Sonar Pro → Tavily → Groq compound fallback
- **Reverse image search**: Google Lens → google_img_source_search → AI fallback

---

## Cybersecurity Capabilities

The bot has deep expertise across:

- **Offensive**: recon, scanning, exploitation, web app testing, password attacks, post-exploitation
- **Defensive**: SOC analysis, threat hunting, DFIR, malware analysis, network defence, hardening
- **Threat Intel**: APT profiling, MITRE ATT&CK, CVE triage, IOC analysis
- **AppSec**: code review, SAST/DAST, secure architecture, threat modelling (STRIDE)
- **Compliance**: ISO 27001, NIST CSF, SOC 2, PCI-DSS, GDPR

---

## Project Structure

```
├── bot.py          # Telegram handlers, routing, commands
├── cli.py          # Interactive terminal client
├── config.py       # Env loading, all settings in one place
├── requirements.txt
├── .env            # Your secrets (never commit this)
└── ai/
    └── Model.py    # All AI logic: chat, vision, voice, search, memory
```
