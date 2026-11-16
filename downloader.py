
import os
import re
import subprocess
import imageio_ffmpeg
import gdown
from faster_whisper import WhisperModel

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Загружаем компактную модель Whisper
whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)



def get_video_info(path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    result = subprocess.run(
        [ffmpeg, "-i", path],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        result.stderr
    )

    if not match:
        raise RuntimeError("Не удалось определить длительность видео")

    hours, minutes, seconds = match.groups()

    return int(
        int(hours) * 3600
        + int(minutes) * 60
        + float(seconds)
    )


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


def transcribe_video(path):
    """
    Распознаёт всю речь в видео.
    Возвращает язык и фразы с таймкодами.
    """

    segments, info = whisper_model.transcribe(
        path,
        beam_size=1,
        word_timestamps=True,
        vad_filter=True
    )

    transcript = []

    for segment in segments:
        transcript.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip()
        })

    return {
        "language": info.language,
        "segments": transcript
    }

