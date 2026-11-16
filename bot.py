
import os
import re
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from downloader import process_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger("SKINVEXX_BOT")

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

process_lock = asyncio.Lock()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 SKINVEXX AI\n\n"
        "Отправь ссылку на своё видео Google Drive.\n\n"
        "Я выполню:\n"
        "🎮 Анализ игрового момента\n"
        "✂️ Автоматическую нарезку\n"
        "📱 Монтаж 9:16\n"
        "🎙 Распознавание речи\n"
        "🌍 Перевод на русский\n"
        "💬 Субтитры\n"
        "📦 Отправку готового MP4\n\n"
        "Команда /help — помощь."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Как пользоваться SKINVEXX:\n\n"
        "1. Загрузи своё видео в Google Drive.\n"
        "2. Открой доступ «Все, у кого есть ссылка».\n"
        "3. Отправь ссылку сюда.\n"
        "4. Дождись обработки и получи MP4.\n\n"
        "Поддерживаются ссылки на файлы Google Drive."
    )


def extract_drive_url(message_text):
    match = re.search(r"https?://\S+", message_text or "")

    if not match:
        return None

    url = match.group(0).rstrip(".,!?)]}")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host not in ("drive.google.com", "www.drive.google.com"):
        raise ValueError("Поддерживаются только ссылки Google Drive.")

    if not re.search(r"/file/d/[a-zA-Z0-9_-]+", url):
        raise ValueError("Нужна ссылка Google Drive на конкретный файл.")

    return url


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message

    if not message or not message.text:
        return

    try:
        url = extract_drive_url(message.text)
    except ValueError as error:
        await message.reply_text(f"❌ {error}")
        return

    if not url:
        await message.reply_text(
            "Пришли ссылку на видео Google Drive."
        )
        return

    status = await message.reply_text(
        "🔥 SKINVEXX получил видео!\n\n"
        "⏳ Добавляю задачу в обработку..."
    )

    async with process_lock:
        try:
            await status.edit_text(
                "📥 СКАЧИВАЮ ВИДЕО\n\n"
                "Подожди, пока исходник загрузится."
            )

            loop = asyncio.get_running_loop()

            # Запускаем тяжёлую обработку отдельно от Telegram.
            result = await loop.run_in_executor(
                None,
                process_video,
                url
            )

            await status.edit_text(
                "✅ ОБРАБОТКА ЗАВЕРШЕНА!\n\n"
                f"🎬 Исходная длительность: "
                f"{result['original_duration']} сек.\n"
                f"✂️ Выбранный фрагмент: "
                f"{result['clip_duration']} сек.\n"
                f"🎙 Язык речи: {result['language']}\n"
                f"💬 Субтитров: {result['segments_count']}\n"
                f"🤖 AI-анализ: "
                f"{'использован' if result['ai_used'] else 'не использован'}\n\n"
                "📤 Отправляю готовое видео..."
            )

            video_path = Path(result["path"])

            if not video_path.exists():
                raise FileNotFoundError(
                    "Итоговый видеофайл не найден."
                )

            with video_path.open("rb") as video:
                await message.reply_video(
                    video=video,
                    caption=(
                        "🔥 SKINVEXX AI\n\n"
                        "Готовый игровой ролик.\n"
                        "📱 Формат: 9:16\n"
                        "🎮 Counter-Strike 2"
                    ),
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60,
                    pool_timeout=60
                )

            await status.edit_text(
                "🚀 SKINVEXX ЗАВЕРШИЛ РАБОТУ!\n\n"
                "Готовое видео отправлено выше."
            )

        except Exception as error:
            logger.exception("Processing failed")

            error_text = str(error).replace(TOKEN, "[скрыто]")

            if len(error_text) > 1200:
                error_text = error_text[:1200]

            await status.edit_text(
                "❌ ОШИБКА ОБРАБОТКИ\n\n"
                f"{error_text}\n\n"
                "Если ошибка непонятна — пришли мне "
                "скриншот логов Render."
            )


async def handle_non_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if update.message:
        await update.message.reply_text(
            "Пока отправляй ссылку Google Drive текстовым сообщением."
        )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.add_handler(
        MessageHandler(
            ~filters.TEXT & ~filters.COMMAND,
            handle_non_text
        )
    )

    logger.info("Starting SKINVEXX Telegram bot")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}",
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
