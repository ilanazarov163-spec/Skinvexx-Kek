
import os
import re
import json
import subprocess
import gdown

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_video_info(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            path
        ],
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)
    return int(float(data["format"]["duration"]))


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
        raise RuntimeError("Google Drive не отдал видео")

    if os.path.getsize(output_path) < 1024:
        raise RuntimeError("Скачанный файл слишком маленький")

    duration = get_video_info(output_path)

    return {
        "path": output_path,
        "title": "Google Drive video",
        "duration": duration,
        "size": os.path.getsize(output_path)
    }
