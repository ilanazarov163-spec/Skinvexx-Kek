
import os
import re
import json
import base64
import logging
import subprocess
import textwrap
from pathlib import Path

import requests
import gdown
import imageio_ffmpeg
from faster_whisper import WhisperModel


# ============================================================
# SKINVEXX — VIDEO PROCESSING ENGINE
# ============================================================

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

COARENA_API_KEY = os.getenv("COARENA_API_KEY", "")
COARENA_BASE_URL = os.getenv(
    "COARENA_BASE_URL",
    "https://coarena.ai/api/v1"
).rstrip("/")
COARENA_MODEL = os.getenv("COARENA_MODEL", "")

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SKINVEXX")

_whisper_model = None


# ============================================================
# WHISPER
# ============================================================

def get_whisper():
    global _whisper_model

    if _whisper_model is None:
        logger.info("Loading Whisper model: %s", WHISPER_MODEL_NAME)

        _whisper_model = WhisperModel(
            WHISPER_MODEL_NAME,
            device="cpu",
            compute_type="int8"
        )

    return _whisper_model


# ============================================================
# FFMPEG HELPERS
# ============================================================

def run_ffmpeg(args):
    command = [FFMPEG] + args

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg error:\n" + result.stderr[-4000:]
        )

    return result


def get_video_info(path):
    result = subprocess.run(
        [FFMPEG, "-i", str(path)],
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

    duration = (
        int(hours) * 3600
        + int(minutes) * 60
        + float(seconds)
    )

    return {
        "duration": duration,
        "duration_int": int(duration)
    }


# ============================================================
# GOOGLE DRIVE DOWNLOAD
# ============================================================

def download_video(url):
    match = re.search(
        r"/file/d/([a-zA-Z0-9_-]+)",
        url
    )

    if not match:
        raise ValueError(
            "Нужна ссылка Google Drive вида /file/d/FILE_ID"
        )

    file_id = match.group(1)

    output_path = DOWNLOAD_DIR / "source.mp4"

    if output_path.exists():
        output_path.unlink()

    downloaded = gdown.download(
        id=file_id,
        output=str(output_path),
        quiet=False
    )

    if not downloaded or not output_path.exists():
        raise RuntimeError("Не удалось скачать видео")

    if output_path.stat().st_size < 1024:
        raise RuntimeError("Скачанный файл пустой или повреждён")

    info = get_video_info(output_path)

    return {
        "path": str(output_path),
        "title": "Google Drive video",
        "duration": info["duration_int"],
        "size": output_path.stat().st_size
    }


# ============================================================
# AI API
# ============================================================

def ai_request(messages, max_tokens=1500):
    if not COARENA_API_KEY:
        raise RuntimeError("Не задан COARENA_API_KEY")

    if not COARENA_MODEL:
        raise RuntimeError(
            "Не задан COARENA_MODEL в переменных Render"
        )

    response = requests.post(
        f"{COARENA_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {COARENA_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": COARENA_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens
        },
        timeout=180
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]


def extract_json(text):
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("AI не вернул JSON")

    return json.loads(text[start:end + 1])


# ============================================================
# FRAME EXTRACTION
# ============================================================

def extract_frames(video_path, duration):
    frames_dir = DOWNLOAD_DIR / "frames"

    if frames_dir.exists():
        for file in frames_dir.iterdir():
            if file.is_file():
                file.unlink()
    else:
        frames_dir.mkdir(parents=True)

    # Один кадр каждые две секунды.
    run_ffmpeg([
        "-y",
        "-i", str(video_path),
        "-vf", "fps=0.5,scale=512:-1",
        "-q:v", "5",
        str(frames_dir / "frame_%04d.jpg")
    ])

    frames = sorted(frames_dir.glob("frame_*.jpg"))

    result = []

    for index, frame in enumerate(frames):
        timestamp = index * 2

        if timestamp >= duration:
            break

        result.append({
            "time": timestamp,
            "path": str(frame)
        })

    return result


# ============================================================
# CS2 MOMENT ANALYSIS
# ============================================================

def analyze_gameplay(video_path, duration):
    """
    Анализирует кадры через Coarena vision-модель.
    Модель должна поддерживать изображения.
    """

    if not COARENA_API_KEY or not COARENA_MODEL:
        logger.warning(
            "Coarena не настроена: используется центральный фрагмент"
        )

        return {
            "start": max(0, (duration - min(duration, 90)) / 2),
            "end": min(duration, 90),
            "reason": "AI analysis is not configured",
            "ai_used": False
        }

    frames = extract_frames(video_path, duration)

    if not frames:
        raise RuntimeError("Не удалось извлечь кадры из видео")

    # Не отправляем слишком много изображений за один запрос.
    if len(frames) > 8:
    step = max(1, len(frames) // 8)
    frames = frames[::step][:8]

    content = [
        {
            "type": "text",
            "text": (
                "Ты анализируешь игровой ролик Counter-Strike 2.\n"
                "На изображениях показаны кадры из одного видео.\n"
                "Время каждого кадра указано перед изображением.\n\n"
                "Найди наиболее интересный непрерывный игровой момент.\n"
                "Приоритет:\n"
                "1. Несколько убийств подряд.\n"
                "2. Клатч 1v2, 1v3, 1v4, 1v5.\n"
                "3. Напряжённая перестрелка.\n"
                "4. Неожиданный фраг или эффектная ситуация.\n"
                "5. Интересный игровой эпизод.\n\n"
                "Выбери интервал продолжительностью от 60 до 120 секунд.\n"
                "Если видео короче 120 секунд, выбери всё видео.\n"
                "Не придумывай события, которых не видно.\n\n"
                "Верни только JSON:\n"
                '{"start": 0, "end": 90, '
                '"reason": "краткое объяснение"}'
            )
        }
    ]

    for frame in frames:
        with open(frame["path"], "rb") as file:
            encoded = base64.b64encode(file.read()).decode("ascii")

        content.append({
            "type": "text",
            "text": f"Время кадра: {frame['time']} секунд"
        })

        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded}"
            }
        })

    answer = ai_request(
        [
            {
                "role": "user",
                "content": content
            }
        ],
        max_tokens=1000
    )

    data = extract_json(answer)

    start = float(data.get("start", 0))
    end = float(data.get("end", duration))

    start = max(0, min(start, duration))
    end = max(start, min(end, duration))

    if end - start < 10:
        raise RuntimeError("AI выбрал слишком короткий фрагмент")

    if end - start > 120:
        end = start + 120

    return {
        "start": start,
        "end": end,
        "reason": str(data.get("reason", "")),
        "ai_used": True
    }


# ============================================================
# SPEECH RECOGNITION
# ============================================================

def transcribe_video(path):
    model = get_whisper()

    segments, info = model.transcribe(
        str(path),
        beam_size=5,
        best_of=5,
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=True
    )

    transcript = []

    for segment in segments:
        text = segment.text.strip()

        if not text:
            continue

        transcript.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": text
        })

    return {
        "language": info.language,
        "segments": transcript
    }


# ============================================================
# TRANSLATION
# ============================================================

def translate_segments(segments, language):
    if not segments:
        return []

    if language and language.lower().startswith("ru"):
        return segments

    if not COARENA_API_KEY or not COARENA_MODEL:
        logger.warning(
            "Перевод пропущен: Coarena не настроена"
        )
        return segments

    source = [
        {
            "id": index,
            "text": item["text"]
        }
        for index, item in enumerate(segments)
    ]

    prompt = (
        "Переведи реплики на естественный русский язык.\n"
        "Сохраняй игровой сленг Counter-Strike 2.\n"
        "Не меняй порядок реплик.\n"
        "Не добавляй пояснения.\n"
        "Верни только JSON такого вида:\n"
        '{"translations":[{"id":0,"text":"перевод"}]}\n\n'
        + json.dumps(source, ensure_ascii=False)
    )

    answer = ai_request(
        [
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=5000
    )

    data = extract_json(answer)

    translations = {
        int(item["id"]): item["text"]
        for item in data.get("translations", [])
        if "id" in item and "text" in item
    }

    result = []

    for index, segment in enumerate(segments):
        result.append({
            **segment,
            "text": translations.get(
                index,
                segment["text"]
            )
        })

    return result


# ============================================================
# ASS SUBTITLES
# ============================================================

def ass_time(seconds):
    centiseconds = max(0, int(seconds * 100))

    hours = centiseconds // 360000
    minutes = (centiseconds // 6000) % 60
    secs = (centiseconds // 100) % 60
    cs = centiseconds % 100

    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def escape_ass(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("\n", " ")
    return text


def create_ass_subtitles(segments, clip_start, clip_end):
    ass_path = DOWNLOAD_DIR / "subtitles.ass"

    header = """[Script Info]
Title: SKINVEXX
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,58,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]

    for segment in segments:
        start = max(
            0,
            float(segment["start"]) - clip_start
        )

        end = min(
            clip_end - clip_start,
            float(segment["end"]) - clip_start
        )

        if end <= start:
            continue

        phrase = escape_ass(segment["text"])

        wrapped = textwrap.wrap(
            phrase,
            width=30,
            break_long_words=False,
            break_on_hyphens=False
        )

        subtitle = r"\N".join(wrapped[:2])

        lines.append(
            "Dialogue: 0,"
            f"{ass_time(start)},"
            f"{ass_time(end)},"
            "Default,,0,0,0,,"
            f"{subtitle}\n"
        )

    ass_path.write_text(
        "".join(lines),
        encoding="utf-8"
    )

    return str(ass_path)


# ============================================================
# VERTICAL VIDEO RENDERING
# ============================================================

def render_vertical_video(
    source_path,
    clip_start,
    clip_end,
    subtitles,
    output_path
):
    ass_path = create_ass_subtitles(
        subtitles,
        clip_start,
        clip_end
    )

    # Размытый фон + исходный кадр целиком по центру.
    # Оригинальная звуковая дорожка сохраняется.

    video_filter = (
        "[0:v]split=2[bg][fg];"
        "[bg]"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "boxblur=22:10[background];"
        "[fg]"
        "scale=1080:1920:force_original_aspect_ratio=decrease"
        "[foreground];"
        "[background][foreground]"
        "overlay=(W-w)/2:(H-h)/2,"
        f"ass={ass_path}"
        "[final]"
    )

    run_ffmpeg([
        "-y",
        "-ss", str(clip_start),
        "-i", str(source_path),
        "-t", str(clip_end - clip_start),
        "-filter_complex", video_filter,
        "-map", "[final]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path)
    ])

    if not Path(output_path).exists():
        raise RuntimeError("Не удалось создать итоговое видео")

    if Path(output_path).stat().st_size < 1024:
        raise RuntimeError("Итоговый видеофайл пустой")

    return str(output_path)


# ============================================================
# COMPLETE PROCESSING PIPELINE
# ============================================================

def process_video(url):
    """
    Полный конвейер:
    скачивание -> анализ -> распознавание -> перевод ->
    монтаж 9:16 -> субтитры -> готовый MP4.
    """

    logger.info("Starting SKINVEXX pipeline")

    source = download_video(url)

    source_path = source["path"]
    duration = source["duration"]

    logger.info("Downloaded video: %s sec", duration)

    # Для короткого ролика используем весь исходник.
    if duration <= 120:
        moment = {
            "start": 0,
            "end": duration,
            "reason": "Видео короче двух минут",
            "ai_used": False
        }
    else:
        moment = analyze_gameplay(
            source_path,
            duration
        )

    clip_start = moment["start"]
    clip_end = moment["end"]

    logger.info(
        "Selected moment: %.2f - %.2f",
        clip_start,
        clip_end
    )

    transcript = transcribe_video(source_path)

    translated = translate_segments(
        transcript["segments"],
        transcript["language"]
    )

    output_path = DOWNLOAD_DIR / "skinvexx_final.mp4"

    render_vertical_video(
        source_path,
        clip_start,
        clip_end,
        translated,
        output_path
    )

    result = {
        "path": str(output_path),
        "title": source["title"],
        "original_duration": duration,
        "clip_start": round(clip_start, 2),
        "clip_end": round(clip_end, 2),
        "clip_duration": round(clip_end - clip_start, 2),
        "language": transcript["language"],
        "segments_count": len(translated),
        "ai_used": moment["ai_used"],
        "reason": moment["reason"],
        "size": output_path.stat().st_size
    }

    logger.info("SKINVEXX processing completed")

    return result
