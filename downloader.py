
import os
import re
import subprocess
import imageio_ffmpeg
import gdown

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_video_info(path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    result = subprocess.run(
        [ffmpeg, "-i", path],
        capture_output=True,
        text=True
    )

    output = result.stderr

    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        output
    )

    if not match:
        raise RuntimeError("Не удалось определить длительность видео")

    hours, minutes, seconds = match.groups()

    duration = (
        int(hours) * 3600
        + int(minutes) * 60
        + float(seconds)
    )

    return int(duration)


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
        raise RuntimeError("Не удалось скачать видео")

    if os.path.getsize(output_path) < 1024:
        raise RuntimeError("Файл слишком маленький")

    duration = get_video_info(output_path)

    return {
        "path": output_path,
        "title": "Google Drive video",
        "duration": duration,
        "size": os.path.getsize(output_path)
    }
