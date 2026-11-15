
import os
import re
import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SKINVEXX BOT запущен!\n\n"
        "Отправь ссылку на YouTube-видео CS2.\n\n"
        "Я подготовлю её для анализа и нарезки.\n\n"
        "Формат результата: TikTok 9:16."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Команды SKINVEXX:\n"
        "/start — запуск бота\n"
        "/help — помощь\n\n"
        "Просто отправь ссылку на YouTube."
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message
    text = message.text or ""

    match = re.search(r"https?://\S+", text)

    if not match:
        await message.reply_text(
            "Отправь ссылку на YouTube-видео."
        )
        return

    url = match.group(0).rstrip(".,!?)]}")

    host = (urlparse(url).hostname or "").lower()

    if host not in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    ):
        await message.reply_text(
            "❌ Пока принимаю только ссылки YouTube."
        )
        return

    await message.reply_text(
        "✅ Ссылку получил!\n\n"
        "Следующий этап — загрузка видео, "
        "поиск интересного момента и автоматический монтаж.\n\n"
        "SKINVEXX готовится к работе 🔥"
    )


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logging.info("SKINVEXX BOT starting...")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=RENDER_URL,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
