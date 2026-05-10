"""
bot.py  –  Telegram bot entry point (upgraded).

New in this version vs original
─────────────────────────────────
• Voice message support   – send a voice note, Whisper transcribes it then AI replies
• Upgraded vision model   – GPT-OSS 120B replaces deprecated Llama 4 Maverick
• Smarter text routing    – auto-picks reasoning model for complex cybersec queries
• Perplexity Sonar Pro    – richer cited web search (replaces Tavily as primary)
• Expanded cybersec help  – /cve, /exploit, /mitre, /hash commands
• All original features preserved (memory, tone, image analysis, reverse search, docs)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    ALLOWED_USER_IDS,
    BOT_TOKEN,
    WEBHOOK_PORT,
    WEBHOOK_SECRET,
    WEBHOOK_URL,
)
from ai.Model import (
    analyze_image,
    ask_ai,
    clear_history,
    find_images_online,
    reverse_image_search,
    reverse_image_search_available,
    synthesize_speech,
    transcribe_voice,
    web_search,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Image memory ───────────────────────────────────────────────────────────────
LAST_IMAGE_KEY             = "last_image"
LAST_IMAGE_MAX_AGE_SECONDS = 15 * 60

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# ── Access control ─────────────────────────────────────────────────────────────
def _is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    user = update.effective_user
    return user is not None and user.id in ALLOWED_USER_IDS


# ── Image memory helpers ───────────────────────────────────────────────────────
def _store_last_image(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    image_bytes: bytes,
    mime_type: str,
    analysis_reply: str,
) -> None:
    context.chat_data[LAST_IMAGE_KEY] = {
        "image_bytes":    image_bytes,
        "mime_type":      mime_type,
        "analysis_reply": analysis_reply,
        "saved_at":       time.time(),
    }


def _get_last_image(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    last_image = context.chat_data.get(LAST_IMAGE_KEY)
    if not last_image:
        return None
    if time.time() - last_image.get("saved_at", 0) > LAST_IMAGE_MAX_AGE_SECONDS:
        context.chat_data.pop(LAST_IMAGE_KEY, None)
        return None
    return last_image


# ── Intent detection ───────────────────────────────────────────────────────────
_SEARCH_TRIGGERS = {
    "search", "google", "look up", "look this up", "find out", "latest",
    "news", "current", "what's happening", "whats happening", "today",
    "right now", "recent", "price of", "score of", "who won",
}

_IMAGE_FOLLOW_TRIGGERS = {
    "find", "find him", "find her", "find this", "find online",
    "find similar", "search online", "who is this", "what is this",
    "reverse search", "find source", "exact match", "source this",
    "trace this", "who made this",
}

_REVERSE_SEARCH_TRIGGERS  = {"reverse search", "find source", "source this", "trace this", "exact match"}
_ONLINE_SEARCH_TRIGGERS   = {
    "find similar", "find online", "search online", "who is this",
    "what is this", "find him", "find her", "find this", "find",
}


def _wants_web_search(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in _SEARCH_TRIGGERS)


def _wants_reverse_image_search(caption: str) -> bool:
    c = caption.lower()
    return any(t in c for t in _REVERSE_SEARCH_TRIGGERS)


def _wants_online_image_search(caption: str) -> bool:
    c = caption.lower()
    return any(t in c for t in _ONLINE_SEARCH_TRIGGERS)


def _should_apply_to_last_image(user_text: str, last_image: dict[str, Any] | None) -> bool:
    if not last_image:
        return False
    text = user_text.strip().lower()
    if not text:
        return False
    if any(p in text for p in _IMAGE_FOLLOW_TRIGGERS):
        return True
    return len(text.split()) <= 6


# ── Reply helpers ──────────────────────────────────────────────────────────────
async def _reply_in_chunks(update: Update, reply: str) -> None:
    if update.message is None:
        return
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])


async def _typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )


def _chat_id(update: Update) -> int:
    chat = update.effective_chat
    return chat.id if chat else 0


def _extract_document_text(file_bytes: bytes, mime_type: str | None) -> str:
    if mime_type == "application/pdf":
        if PdfReader is None:
            return ""
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        pages: list[str] = []
        for page in reader.pages[:10]:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)[:8000]
    return file_bytes.decode("utf-8", errors="ignore")[:8000]


# ── Command handlers ───────────────────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await _reply_in_chunks(
        update,
        "Hey! I'm your AI assistant 👋\n\n"
        "I specialise in cybersecurity but can help with anything.\n"
        "Send me text, a photo, a voice note, or a file.\n\n"
        "Use /help to see all commands.",
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    text = (
        "Here's what I can do:\n\n"
        "💬 *Chat* – talk to me, I remember our conversation\n"
        "🎙 *Voice* – send a voice note and I'll transcribe + reply\n"
        "📷 *Photo* – send a photo and I'll analyse it\n"
        "   • Caption: 'who is this?' or 'find online'\n"
        "📄 *Document* – send a PDF/text file to analyse\n\n"
        "*Commands*\n"
        "/search <query> – live web search (Perplexity Sonar)\n"
        "/image <query> – find image pages online\n"
        "/cve <id> – look up a CVE (e.g. /cve CVE-2024-1234)\n"
        "/exploit <term> – search for exploits/PoCs\n"
        "/mitre <technique> – look up a MITRE ATT&CK technique\n"
        "/hash <hash> – check a file hash reputation\n"
        "/clear – forget our conversation\n"
        "/help – this message"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    clear_history(_chat_id(update))
    context.chat_data.pop(LAST_IMAGE_KEY, None)
    await _reply_in_chunks(update, "Memory cleared! Fresh start 🧹")


async def handle_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await _reply_in_chunks(update, "Usage: `/search <query>`")
        return
    await _typing(update, context)
    reply = await web_search(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


async def handle_image_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await _reply_in_chunks(update, "Usage: `/image <query>`")
        return
    await _typing(update, context)
    reply = await find_images_online(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


async def handle_cve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cve <CVE-ID> — fetch CVE details, CVSS, affected versions, and mitigations."""
    if not _is_allowed(update):
        return
    cve_id = " ".join(context.args).strip() if context.args else ""
    if not cve_id:
        await _reply_in_chunks(update, "Usage: `/cve CVE-2024-1234`")
        return
    await _typing(update, context)
    query = (
        f"Look up {cve_id}: provide the vulnerability description, CVSS score, "
        f"affected products and versions, exploit availability, and recommended mitigations."
    )
    reply = await web_search(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


async def handle_exploit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/exploit <term> — search for exploits and PoCs."""
    if not _is_allowed(update):
        return
    term = " ".join(context.args).strip() if context.args else ""
    if not term:
        await _reply_in_chunks(update, "Usage: `/exploit <service/CVE/software>`")
        return
    await _typing(update, context)
    query = (
        f"Find public exploits, proof-of-concept code, and Metasploit modules for: {term}. "
        "Include exploit-db IDs, GitHub links, and any relevant CVEs."
    )
    reply = await web_search(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


async def handle_mitre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/mitre <technique ID or name> — look up MITRE ATT&CK technique."""
    if not _is_allowed(update):
        return
    technique = " ".join(context.args).strip() if context.args else ""
    if not technique:
        await _reply_in_chunks(update, "Usage: `/mitre T1059` or `/mitre spearphishing`")
        return
    await _typing(update, context)
    query = (
        f"Look up MITRE ATT&CK technique: {technique}. "
        "Provide the technique ID, tactic, description, real-world usage examples, "
        "detection methods, and mitigation strategies."
    )
    reply = await ask_ai(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


async def handle_hash(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/hash <md5/sha1/sha256> — check hash reputation via search."""
    if not _is_allowed(update):
        return
    hash_val = " ".join(context.args).strip() if context.args else ""
    if not hash_val:
        await _reply_in_chunks(update, "Usage: `/hash <MD5 or SHA256>`")
        return
    await _typing(update, context)
    query = (
        f"Check the reputation of this file hash: {hash_val}. "
        "Search VirusTotal, MalwareBazaar, and threat intelligence sources. "
        "Is it known malware? What family? What behaviour?"
    )
    reply = await web_search(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


# ── Message handler ────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update) or update.message is None:
        return

    user_text = update.message.text
    if not user_text:
        return

    await _typing(update, context)
    cid = _chat_id(update)

    last_image = _get_last_image(context)
    if _should_apply_to_last_image(user_text, last_image):
        try:
            await _handle_last_image_followup(update, context, user_text, last_image)
            return
        except Exception as exc:
            logger.exception("Failed image follow-up: %s", exc)
            await _reply_in_chunks(update, "⚠️ Something went wrong with the image follow-up.")
            return

    if _wants_web_search(user_text):
        try:
            reply = await web_search(user_text, chat_id=cid)
        except Exception as exc:
            logger.exception("Web search error: %s", exc)
            reply = "⚠️ Couldn't complete the search right now."
    else:
        try:
            reply = await ask_ai(user_text, chat_id=cid)
        except Exception as exc:
            logger.exception("AI error: %s", exc)
            reply = "⚠️ Something went wrong. Try again?"

    if not reply or not reply.strip():
        reply = "⚠️ Got an empty response from the AI."

    await _reply_in_chunks(update, reply)


async def _handle_last_image_followup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    last_image: dict[str, Any],
) -> None:
    image_bytes    = last_image["image_bytes"]
    mime_type      = last_image["mime_type"]
    analysis_reply = last_image.get("analysis_reply", "")
    cid            = _chat_id(update)

    if _wants_reverse_image_search(user_text) or _wants_online_image_search(user_text):
        reverse_reply = await reverse_image_search(
            image_bytes=image_bytes,
            analysis_text=analysis_reply,
            chat_id=cid,
        )
        reply = f"{analysis_reply}\n\n{reverse_reply}" if analysis_reply else reverse_reply
    else:
        reply = await analyze_image(
            prompt=user_text,
            image_bytes=image_bytes,
            mime_type=mime_type,
            chat_id=cid,
        )
        context.chat_data[LAST_IMAGE_KEY]["analysis_reply"] = reply

    await _reply_in_chunks(update, reply)


# ── Voice handler ──────────────────────────────────────────────────────────────
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Full voice pipeline:
      1. Download the voice note
      2. Transcribe with Groq Whisper Large v3 Turbo (STT)
      3. Generate AI reply (text)
      4. Synthesise reply with Groq Orpheus v1 (TTS)
      5. Send back as a voice note — voice in, voice out
    """
    if not _is_allowed(update) or update.message is None:
        return
    if not update.message.voice and not update.message.audio:
        return

    await _typing(update, context)
    cid = _chat_id(update)

    try:
        voice_obj   = update.message.voice or update.message.audio
        tg_file     = await context.bot.get_file(voice_obj.file_id)
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        mime_type   = getattr(voice_obj, "mime_type", None) or "audio/ogg"

        # ── Step 1: Transcribe ─────────────────────────────────────────────────
        transcript = await transcribe_voice(audio_bytes, mime_type)
        if not transcript:
            await _reply_in_chunks(update, "⚠️ Couldn't transcribe that audio. Try again?")
            return

        # ── Step 2: Generate AI reply ──────────────────────────────────────────
        if _wants_web_search(transcript):
            reply_text = await web_search(transcript, chat_id=cid)
        else:
            reply_text = await ask_ai(transcript, chat_id=cid)

        if not reply_text or not reply_text.strip():
            reply_text = "I couldn't generate a response for that."

        # ── Step 3: Synthesise to speech ───────────────────────────────────────
        wav_bytes = await synthesize_speech(reply_text)

        if wav_bytes and update.effective_chat:
            import io
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=io.BytesIO(wav_bytes),
                caption=None,
            )
        else:
            # TTS failed — fall back to text reply
            await _reply_in_chunks(update, reply_text)

    except Exception as exc:
        logger.exception("Voice handler error: %s", exc)
        await _reply_in_chunks(update, "⚠️ Something went wrong processing the voice message.")


# ── Photo handler ──────────────────────────────────────────────────────────────
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update) or update.message is None or not update.message.photo:
        return

    caption = update.message.caption or ""
    prompt  = caption or "Analyze this image and describe what you see."
    cid     = _chat_id(update)

    await _typing(update, context)

    try:
        photo      = update.message.photo[-1]
        tg_file    = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await tg_file.download_as_bytearray())
        mime_type   = "image/jpeg"

        analysis_reply = await analyze_image(
            prompt=prompt, image_bytes=image_bytes, mime_type=mime_type, chat_id=cid,
        )
        _store_last_image(
            context, image_bytes=image_bytes, mime_type=mime_type, analysis_reply=analysis_reply,
        )
        reply = analysis_reply

        if _wants_reverse_image_search(caption):
            reverse_reply = await reverse_image_search(
                image_bytes=image_bytes, analysis_text=analysis_reply, chat_id=cid,
            )
            reply = f"{analysis_reply}\n\n{reverse_reply}"
        elif _wants_online_image_search(caption):
            if reverse_image_search_available():
                reverse_reply = await reverse_image_search(
                    image_bytes=image_bytes, analysis_text=analysis_reply, chat_id=cid,
                )
                reply = f"{analysis_reply}\n\n{reverse_reply}"
            else:
                search_reply = await find_images_online(
                    f"Find pages with images matching: {analysis_reply}", chat_id=cid,
                )
                reply = f"{analysis_reply}\n\nOnline matches:\n{search_reply}"

    except Exception as exc:
        logger.exception("Failed to analyse photo: %s", exc)
        reply = "⚠️ Something went wrong while analysing that image."

    await _reply_in_chunks(update, reply)


# ── Document handler ───────────────────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update) or update.message is None or not update.message.document:
        return

    doc     = update.message.document
    caption = update.message.caption or ""
    cid     = _chat_id(update)

    SUPPORTED_MIME_PREFIXES = ("text/", "application/pdf", "application/json", "image/")
    if not any(doc.mime_type and doc.mime_type.startswith(p) for p in SUPPORTED_MIME_PREFIXES):
        await _reply_in_chunks(update, "I can read text files and PDFs. Send me one of those!")
        return

    await _typing(update, context)

    try:
        tg_file    = await context.bot.get_file(doc.file_id)
        file_bytes = bytes(await tg_file.download_as_bytearray())

        if doc.mime_type and doc.mime_type.startswith("image/"):
            analysis = await analyze_image(
                prompt=caption or "Analyze this document image.",
                image_bytes=file_bytes,
                mime_type=doc.mime_type,
                chat_id=cid,
            )
        else:
            file_text = _extract_document_text(file_bytes, doc.mime_type)
            if not file_text.strip():
                if doc.mime_type == "application/pdf" and PdfReader is None:
                    await _reply_in_chunks(
                        update,
                        "PDF support needs `pypdf`. Run `pip install -r requirements.txt`.",
                    )
                    return
                await _reply_in_chunks(update, "I couldn't extract readable text from that file.")
                return

            user_prompt = (
                f"{caption}\n\nFile content:\n{file_text}"
                if caption
                else f"Analyze this file:\n{file_text}"
            )
            analysis = await ask_ai(user_prompt, chat_id=cid)

        await _reply_in_chunks(update, analysis)

    except Exception as exc:
        logger.exception("Failed to process document: %s", exc)
        await _reply_in_chunks(update, "⚠️ Couldn't read that file. Is it a valid text/PDF?")


# ── App builder ────────────────────────────────────────────────────────────────
def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Add it to your .env file.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Standard commands
    app.add_handler(CommandHandler("start",   handle_start))
    app.add_handler(CommandHandler("help",    handle_help))
    app.add_handler(CommandHandler("clear",   handle_clear))
    app.add_handler(CommandHandler("search",  handle_search_command))
    app.add_handler(CommandHandler("image",   handle_image_search))

    # Cybersecurity commands
    app.add_handler(CommandHandler("cve",     handle_cve))
    app.add_handler(CommandHandler("exploit", handle_exploit))
    app.add_handler(CommandHandler("mitre",   handle_mitre))
    app.add_handler(CommandHandler("hash",    handle_hash))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO,                   handle_image))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,   handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL,            handle_document))

    if WEBHOOK_URL:
        logger.info("Starting in webhook mode → %s", WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            secret_token=WEBHOOK_SECRET or None,
            webhook_url=WEBHOOK_URL,
        )
    else:
        logger.info("Bot is online and polling…")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
