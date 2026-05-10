"""
bot.py  –  Telegram bot entry point.

New features vs. original
──────────────────────────
• Conversation memory       – bot remembers the full thread, not just the last image
• Tone matching             – casual users get casual replies; technical → structured
• /search command           – explicit web search from Telegram
• /clear command            – wipe conversation memory for current chat
• /help command             – shows all available commands
• Access control            – optional allowlist via ALLOWED_USER_IDS in .env
• Webhook support           – set WEBHOOK_URL in .env to run without polling
• Typing indicator          – shows "typing…" while the AI thinks
• Document/file analysis    – auto-analyzes PDFs/text files sent to the bot
• Inline image follow-up    – unchanged but now passes chat_id for memory context
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
    web_search,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Image memory ───────────────────────────────────────────────────────────────
LAST_IMAGE_KEY = "last_image"
LAST_IMAGE_MAX_AGE_SECONDS = 15 * 60


# ── Access control ─────────────────────────────────────────────────────────────
def _is_allowed(update: Update) -> bool:
    """Return True if the user is permitted to use the bot."""
    if not ALLOWED_USER_IDS:
        return True  # Open to everyone
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
        "image_bytes": image_bytes,
        "mime_type": mime_type,
        "analysis_reply": analysis_reply,
        "saved_at": time.time(),
    }


def _get_last_image(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    last_image = context.chat_data.get(LAST_IMAGE_KEY)
    if not last_image:
        return None
    if time.time() - last_image.get("saved_at", 0) > LAST_IMAGE_MAX_AGE_SECONDS:
        context.chat_data.pop(LAST_IMAGE_KEY, None)
        return None
    return last_image


# ── Intent detection helpers ───────────────────────────────────────────────────
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

_REVERSE_SEARCH_TRIGGERS = {"reverse search", "find source", "source this", "trace this", "exact match"}
_ONLINE_SEARCH_TRIGGERS = {"find similar", "find online", "search online", "who is this",
                            "what is this", "find him", "find her", "find this", "find"}


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
    # Short follow-ups right after an image likely refer to it
    return len(text.split()) <= 6


# ── Reply helpers ──────────────────────────────────────────────────────────────
async def _reply_in_chunks(update: Update, reply: str) -> None:
    if update.message is None:
        return
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])


async def _typing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a typing action to show the bot is working."""
    if update.effective_chat:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )


def _chat_id(update: Update) -> int:
    chat = update.effective_chat
    return chat.id if chat else 0


# ── Command handlers ───────────────────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    await _reply_in_chunks(
        update,
        "Hey! I'm your AI assistant 👋\n\n"
        "Just talk to me normally. Send me a photo and I'll analyze it. "
        "Use /help to see all commands.",
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update):
        return
    text = (
        "Here's what I can do:\n\n"
        "💬 *Chat* – just talk to me, I remember our conversation\n"
        "📷 *Photo* – send a photo and I'll analyze it\n"
        "   • Add a caption like 'who is this?' or 'find online'\n"
        "   • After an image, follow-up messages work too\n"
        "/search <query> – search the web\n"
        "/image <query> – find image pages online\n"
        "/clear – forget our conversation and start fresh\n"
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
    """Explicit /search command."""
    if not _is_allowed(update):
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await _reply_in_chunks(update, "What do you want me to search? Usage: `/search <query>`")
        return
    await _typing(update, context)
    cid = _chat_id(update)
    reply = await web_search(query, chat_id=cid)
    await _reply_in_chunks(update, reply)


async def handle_image_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/image command – find image pages online."""
    if not _is_allowed(update):
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await _reply_in_chunks(update, "What images do you want to find? Usage: `/image <query>`")
        return
    await _typing(update, context)
    reply = await find_images_online(query, chat_id=_chat_id(update))
    await _reply_in_chunks(update, reply)


# ── Message handler ────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages."""
    if not _is_allowed(update):
        return
    if update.message is None:
        return

    user_text = update.message.text
    if not user_text:
        return

    await _typing(update, context)
    cid = _chat_id(update)

    # Check if this message refers to the last image
    last_image = _get_last_image(context)
    if _should_apply_to_last_image(user_text, last_image):
        try:
            await _handle_last_image_followup(update, context, user_text, last_image)
            return
        except Exception as exc:
            logger.exception("Failed image follow-up: %s", exc)
            await _reply_in_chunks(update, "⚠️ Something went wrong with the image follow-up.")
            return

    # Route to web search if user wants live info
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
    image_bytes = last_image["image_bytes"]
    mime_type = last_image["mime_type"]
    analysis_reply = last_image.get("analysis_reply", "")
    cid = _chat_id(update)

    if _wants_reverse_image_search(user_text) or _wants_online_image_search(user_text):
        reverse_reply = await reverse_image_search(
            image_bytes=image_bytes,
            analysis_text=analysis_reply,
            chat_id=cid,
        )
        reply = (
            f"{analysis_reply}\n\n{reverse_reply}"
            if analysis_reply
            else reverse_reply
        )
    else:
        reply = await analyze_image(
            prompt=user_text,
            image_bytes=image_bytes,
            mime_type=mime_type,
            chat_id=cid,
        )
        context.chat_data[LAST_IMAGE_KEY]["analysis_reply"] = reply

    await _reply_in_chunks(update, reply)


# ── Photo handler ──────────────────────────────────────────────────────────────
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze photos sent to the bot."""
    if not _is_allowed(update):
        return
    if update.message is None or not update.message.photo:
        return

    caption = update.message.caption or ""
    prompt = caption or "Analyze this image and describe what you see."
    cid = _chat_id(update)

    await _typing(update, context)

    try:
        photo = update.message.photo[-1]
        telegram_file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await telegram_file.download_as_bytearray())
        mime_type = "image/jpeg"

        analysis_reply = await analyze_image(
            prompt=prompt,
            image_bytes=image_bytes,
            mime_type=mime_type,
            chat_id=cid,
        )
        _store_last_image(
            context,
            image_bytes=image_bytes,
            mime_type=mime_type,
            analysis_reply=analysis_reply,
        )
        reply = analysis_reply

        if _wants_reverse_image_search(caption):
            reverse_reply = await reverse_image_search(
                image_bytes=image_bytes,
                analysis_text=analysis_reply,
                chat_id=cid,
            )
            reply = f"{analysis_reply}\n\n{reverse_reply}"
        elif _wants_online_image_search(caption):
            if reverse_image_search_available():
                reverse_reply = await reverse_image_search(
                    image_bytes=image_bytes,
                    analysis_text=analysis_reply,
                    chat_id=cid,
                )
                reply = f"{analysis_reply}\n\n{reverse_reply}"
            else:
                search_reply = await find_images_online(
                    f"Find pages with images matching this description: {analysis_reply}",
                    chat_id=cid,
                )
                reply = f"{analysis_reply}\n\nOnline matches:\n{search_reply}"

    except Exception as exc:
        logger.exception("Failed to analyze photo: %s", exc)
        reply = "⚠️ Something went wrong while analyzing that image."

    await _reply_in_chunks(update, reply)


# ── Document handler ───────────────────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle documents (PDF, text files, etc.) by asking the AI to analyze them."""
    if not _is_allowed(update):
        return
    if update.message is None or not update.message.document:
        return

    doc = update.message.document
    caption = update.message.caption or ""
    cid = _chat_id(update)

    # Only handle text/PDF; skip binaries
    SUPPORTED_MIME_PREFIXES = ("text/", "application/pdf", "application/json")
    if not any(doc.mime_type and doc.mime_type.startswith(p) for p in SUPPORTED_MIME_PREFIXES):
        await _reply_in_chunks(
            update,
            "I can read text files and PDFs. Send me one of those!",
        )
        return

    await _typing(update, context)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = bytes(await tg_file.download_as_bytearray())

        if doc.mime_type and doc.mime_type.startswith("image/"):
            # Treat as image
            analysis = await analyze_image(
                prompt=caption or "Analyze this document image.",
                image_bytes=file_bytes,
                mime_type=doc.mime_type,
                chat_id=cid,
            )
        else:
            try:
                file_text = file_bytes.decode("utf-8", errors="ignore")[:8000]
            except Exception:
                file_text = "[Could not decode file content]"

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

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(CommandHandler("search", handle_search_command))
    app.add_handler(CommandHandler("image", handle_image_search))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

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
