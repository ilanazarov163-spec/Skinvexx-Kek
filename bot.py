
import os
import re
import asyncio
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

from downloader import download_video

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))

download_lock = asyncio.Lock()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SKINVEXX BOT\n\n"
        "Отправь ссылку на YouTube с CS2.\n"
        "Я загружу видео и подготовлю его к анализу."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправь ссылку на YouTube.\n"
        "Поддерживаются youtube.com и youtu.be."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    match = re.search(r"https?://\S+", message.text or "")

    if not match:
        await message.reply_text("Пришли ссылку на YouTube.")
        return

    url = match.group(0).rstrip(".,!?)]}")
    host = (urlparse(url).hostname or "").lower()

    if host not in ("youtube.com", "www.youtube.com",
                    "m.youtube.com", "youtu.be", "www.youtu.be"):
        await message.reply_text("❌ Нужна ссылка на YouTube.")
        return

    status = await message.reply_text(
        "⏳ Получил ссылку!\nНачинаю загрузку видео..."
    )

    try:
        async with download_lock:
            result = await asyncio.to_thread(download_video, url)

        duration = int(result.get("duration") or 0)
        minutes, seconds = divmod(duration, 60)

        await status.edit_text(
            "✅ ВИДЕО ЗАГРУЖЕНО!\n\n"
            f"🎬 {result['title']}\n"
            f"⏱ Длительность: {minutes}:{seconds:02d}\n\n"
            "Следующий этап: AI-анализ и поиск лучшего момента."
        )

    except Exception:
        logging.exception("Video download failed")
        await status.edit_text(
            "❌ Не удалось загрузить видео.\n"
            "Возможно, оно недоступно или загрузка не поддерживается."
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=RENDER_URL,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
