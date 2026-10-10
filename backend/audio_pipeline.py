"""Local microphone capture and offline text-to-speech helpers.

The module intentionally keeps audio dependencies optional.  ``sounddevice``
is loaded only when recording starts and ``pyttsx3`` only when speech starts,
so importing the module does not require audio hardware.
"""

from __future__ import annotations

import array
import threading
import time
import wave
from pathlib import Path
from queue import Empty, Queue
from typing import Any

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
BLOCK_SIZE = 1_600
SILENCE_SECONDS = 1.5
RMS_THRESHOLD = 500


def _rms_int16(data: bytes) -> float:
    samples = array.array("h")
    samples.frombytes(data)
    if not samples:
        return 0.0
    return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5


def record_audio(
    output_path: str = "temp_audio/input.wav",
    max_seconds: int = 15,
    interactive: bool = False,
) -> str:
    """Record mono 16 kHz 16-bit PCM WAV audio and return its file path.

    By default, recording starts immediately and uses VAD/silence detection.
    When ``interactive`` is true, Enter starts recording and a second Enter
    stops it manually; VAD and the maximum duration remain safety fallbacks.
    """
    if max_seconds <= 0:
        raise ValueError("max_seconds must be greater than zero")

    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Recording requires the offline sounddevice package. "
            "Install it with: pip install sounddevice"
        ) from exc

    if interactive:
        input("Press Enter to start recording...")

    blocks: Queue[bytes] = Queue()
    stop_event = threading.Event()

    def callback(indata: Any, frames: int, callback_time: Any, status: Any) -> None:
        del frames, callback_time
        if status:
            print(f"Audio input warning: {status}")
        blocks.put(indata.tobytes())

    def wait_for_manual_stop() -> None:
        try:
            input("Recording... press Enter to stop.")
        except EOFError:
            # Non-interactive environments rely on silence or max_seconds.
            return
        stop_event.set()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    captured = bytearray()
    speech_detected = False
    silence_started: float | None = None
    started_at = time.monotonic()
    stop_thread: threading.Thread | None = None

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=callback,
        ):
            if interactive:
                stop_thread = threading.Thread(
                    target=wait_for_manual_stop,
                    name="audio-stop-listener",
                    daemon=True,
                )
                stop_thread.start()

            while not stop_event.is_set():
                if time.monotonic() - started_at >= max_seconds:
                    break
                try:
                    block = blocks.get(timeout=0.1)
                except Empty:
                    continue

                captured.extend(block)
                if _rms_int16(block) >= RMS_THRESHOLD:
                    speech_detected = True
                    silence_started = None
                elif speech_detected:
                    silence_started = silence_started or time.monotonic()
                    if time.monotonic() - silence_started >= SILENCE_SECONDS:
                        break
    except OSError as exc:
        raise RuntimeError(f"Unable to access the microphone: {exc}") from exc

    if not captured:
        raise RuntimeError("No audio was captured from the microphone")

    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(captured)

    return str(output)


def _speak_with_pyttsx3(text: str) -> None:
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError(
            "Offline TTS requires pyttsx3. Install it with: pip install pyttsx3"
        ) from exc

    engine = pyttsx3.init()
    try:
        engine.say(text)
        engine.runAndWait()
    finally:
        engine.stop()


def speak_tts(text: str, blocking: bool = True) -> None:
    """Speak text through the local device speaker using offline TTS."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    if blocking:
        _speak_with_pyttsx3(text)
        return

    threading.Thread(
        target=_speak_with_pyttsx3,
        args=(text,),
        name="offline-tts",
        daemon=True,
    ).start()
