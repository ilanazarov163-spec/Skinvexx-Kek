
import os
import re
import gdown

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_video(url):
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)

    if not match:
        raise ValueError("Неправильная ссылка Google Drive")

    file_id = match.group(1)
    output_path = os.path.join(DOWNLOAD_DIR, "source.mp4")

    if os.path.exists(output_path):
        os.remove(output_path)

    downloaded = gdown.download(
        id=file_id,
        output=output_path,
        quiet=False
    )

    if not downloaded or not os.path.exists(output_path):
        raise RuntimeError(
            "Не удалось скачать файл. Проверь доступ Google Drive."
        )

    return {
        "path": output_path,
        "title": "Google Drive video",
        "duration": 0,
    }
