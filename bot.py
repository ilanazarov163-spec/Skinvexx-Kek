
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

from downloader import download_video, transcribe_video

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))

process_lock = asyncio.Lock()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SKINVEXX BOT\n\n"
        "Отправь ссылку на видео из Google Drive."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправь ссылку на видео из Google Drive.\n"
        "Доступ должен быть открыт для всех, у кого есть ссылка."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    match = re.search(r"https?://\S+", message.text or "")

    if not match:
        await message.reply_text("Пришли ссылку на Google Drive.")
        return

    url = match.group(0).rstrip(".,!?)]}")
    host = (urlparse(url).hostname or "").lower()

    if host not in ("drive.google.com", "www.drive.google.com"):
        await message.reply_text("❌ Сейчас поддерживаются ссылки Google Drive.")
        return

    if not re.search(r"/file/d/[a-zA-Z0-9_-]+", url):
        await message.reply_text("❌ Нужна прямая ссылка на файл Google Drive.")
        return

    status = await message.reply_text(
        "⏳ Получил ссылку!\nЗагружаю видео..."
    )

    try:
        async with process_lock:
            result = await asyncio.to_thread(download_video, url)

            await status.edit_text(
                "✅ Видео загружено!\n\n"
                "🎙 Начинаю распознавать всю речь.\n"
                "Это может занять некоторое время..."
            )

            transcript = await asyncio.to_thread(
                transcribe_video,
                result["path"]
            )

        language = transcript["language"]
        segments = transcript["segments"]

        if segments:
            full_text = "\n".join(
                f"[{item['start']:.2f}–{item['end']:.2f}] {item['text']}"
                for item in segments
            )
        else:
            full_text = "Речь не обнаружена."

        preview = full_text[:3000]

        await status.edit_text(
            "✅ РАСПОЗНАВАНИЕ ЗАВЕРШЕНО!\n\n"
            f"🎬 Видео: {result['title']}\n"
            f"⏱ Длительность: {result['duration']} сек.\n"
            f"🌐 Язык речи: {language}\n"
            f"📝 Фрагментов речи: {len(segments)}\n\n"
            f"{preview}"
        )

    except Exception:
        logging.exception("Video processing failed")
        await status.edit_text(
            "❌ Ошибка при обработке видео.\n"
            "Посмотри логи Render."
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
        webhook_url=f"{RENDER_URL}/{TOKEN}",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
