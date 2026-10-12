"""Automatic Speech Recognition using faster-whisper (CTranslate2).

Drop-in replacement for the old transformers-based whisper.py.

Uses faster-whisper with anti-hallucination parameters:
    - VAD filter (skips silence, prevents phantom transcriptions)
    - condition_on_previous_text=False (stops loop propagation)
    - no_speech_threshold / compression_ratio_threshold / log_prob_threshold
    - repetition guard on the final text

Audio is converted to 16 kHz mono WAV via the FFmpeg binary bundled
with imageio-ffmpeg before being passed to faster-whisper.
"""

from functools import lru_cache
from pathlib import Path
import re
import tempfile
import subprocess

FINETUNED_MODEL_DIR = Path("models/whisper_finetuned")
CT2_MODEL_DIR = Path("models/whisper_swahili_ct2")
DEFAULT_MODEL = "small"


@lru_cache(maxsize=2)
def load_model(model_size: str = DEFAULT_MODEL):
    """Load a faster-whisper model.

    Priority:
        1. Fine-tuned CT2 model at models/whisper_swahili_ct2
        2. faster-whisper short name (e.g. "small")
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("Warning: faster-whisper not installed. Install with: pip install faster-whisper")
        return None

    if CT2_MODEL_DIR.exists() and (CT2_MODEL_DIR / "model.bin").exists():
        model_id = str(CT2_MODEL_DIR)
        print(f"Loading fine-tuned CT2 model from {model_id}")
    else:
        model_id = model_size
        print(f"Loading faster-whisper model: {model_id}")

    try:
        model = WhisperModel(
            model_id,
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
        )
    except Exception as e:
        print(f"Warning: could not load faster-whisper model {model_id}: {e}")
        return None

    return model


def convert_to_wav(audio_path):
    """Convert any audio to 16 kHz mono WAV using bundled FFmpeg."""
    from imageio_ffmpeg import get_ffmpeg_exe

    ffmpeg_exe = get_ffmpeg_exe()
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav.close()

    command = [
        ffmpeg_exe,
        "-y",
        "-i", str(audio_path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        temp_wav.name,
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=True,
    )
    return Path(temp_wav.name)


def _deduplicate_repeats(text: str) -> str:
    """Collapse pathological repetition loops."""
    if not text:
        return text
    text = re.sub(r"\b(\w)([.\s]+\1){3,}\b", r"\1", text)
    text = re.sub(r"\b(\S+)(\s+\1){3,}\b", r"\1", text)
    return text.strip()


def transcribe(
    audio_path,
    model_size: str = DEFAULT_MODEL,
    language: str = "sw",
    task: str = "transcribe",
):
    """Transcribe audio to text using faster-whisper.

    Preserves the old signature so main.py does not need changes.
    """
    model = load_model(model_size)
    if model is None:
        return ""

    audio = Path(audio_path)
    converted_path = None

    if audio.suffix.lower() != ".wav":
        try:
            converted_path = convert_to_wav(audio)
            audio_to_use = converted_path
        except Exception as e:
            print(f"Warning: could not convert {audio_path}: {e}")
            return ""
    else:
        audio_to_use = audio

    try:
        segments, info = model.transcribe(
            str(audio_to_use),
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            temperature=0.0,
            without_timestamps=True,
        )

        parts = [seg.text.strip() for seg in segments if seg.text.strip()]
        text = " ".join(parts).strip()
        text = _deduplicate_repeats(text)

    except Exception as e:
        print(f"Warning: transcription failed: {e}")
        return ""

    finally:
        if converted_path is not None:
            converted_path.unlink(missing_ok=True)

    return text
