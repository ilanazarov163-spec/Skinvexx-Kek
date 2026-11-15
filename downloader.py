
import os
import yt_dlp


DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_video(url):
    options = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "merge_output_format": "mp4",
        "outtmpl": f"{DOWNLOAD_DIR}/source.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)

    return {
        "path": os.path.join(DOWNLOAD_DIR, "source.mp4"),
        "title": info.get("title", "CS2 video"),
        "duration": info.get("duration", 0),
    }
