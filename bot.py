import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN
from ai.Model import ask_ai

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages by forwarding them to the AI and replying."""
    if update.message is None:
        logger.debug("Received update without a message; ignoring.")
        return

    user_text = update.message.text
    if not user_text:
        logger.debug("Received message without text; ignoring.")
        return

    try:
        reply = await ask_ai(user_text)
    except Exception as exc:
        logger.exception("Failed to get AI response: %s", exc)
        reply = "⚠️ Something went wrong while generating the response."

    if not reply or not reply.strip():
        reply = "⚠️ The AI returned an empty response."

    # Telegram message limit protection (4096 chars, using 4000 for safety margin)
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is online and polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
