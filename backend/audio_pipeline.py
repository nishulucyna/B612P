"""Local microphone capture and offline text-to-speech helpers.

The module intentionally keeps audio dependencies optional.  ``sounddevice``
is loaded only when recording starts and ``pyttsx3`` only when speech starts,
so importing the module does not require audio hardware.

Microphone capture: on Windows the default capture path (MME at 16 kHz) runs the signal through
the driver's noise suppression / gain control and a low-quality sample-rate conversion, which
turned clear speech into mush for the speech recogniser. ``record_audio`` therefore first tries a
raw WASAPI exclusive-mode stream at the microphone's native rate (resampled to 16 kHz with a proper
filter afterwards) and falls back to the plain 16 kHz default input if that cannot be opened.
Environment: ``AUDIO_INPUT=legacy`` forces the plain path; ``AUDIO_INPUT_DEVICE=<index>`` picks the
WASAPI input device (see ``python -m sounddevice``).
"""

from __future__ import annotations

import math
import os
import threading
import time
import wave
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import numpy as np

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2
BLOCK_SIZE = 1_600             # 0.1 s at 16 kHz
BLOCK_SECONDS = 0.1
SILENCE_SECONDS = 1.8
RMS_THRESHOLD = 100            # minimum level (int16 units) that counts as speech
MAX_RMS_THRESHOLD = 3000       # never demand more than this, even in a loud room
NOISE_MARGIN = 2.2             # speech must be this many times louder than the room (~7 dB)
CALIBRATION_SECONDS = 0.5      # audio needed before any speech/pause decision
NOISE_PERCENTILE = 20          # room noise = the quietest fifth of the blocks heard so far...
NOISE_FLOOR_CAP = 1000         # ...but never assume the room is louder than this (int16 RMS)
MIN_LOUD_BLOCKS = 4            # at least 0.4 s of speech before a pause may end the recording
MIN_SPEECH_BLOCKS = 2          # consecutive loud blocks needed (ignores single spikes)
QUIET_FRACTION = 0.85          # a pause = this share of the last SILENCE_SECONDS is quiet (ignores clicks)
QUIET_RATIO = 0.6              # 'quiet' means below this fraction of the speech threshold (hysteresis:
                               # faint words flickering around the threshold are not a pause)
TARGET_PEAK = 0.8              # recorded audio is scaled so its loud parts reach 80% of full scale
MAX_GAIN = 30.0                # but never amplified more than this (room noise only)
TRIM_BEFORE_BLOCKS = 5         # keep 0.5 s before the first speech...
TRIM_AFTER_BLOCKS = 7          # ...and 0.7 s after the last speech; drop the noise around it

#: Description of the input path used by the most recent recording (for diagnostics).
last_input_description = ""


@dataclass
class _InputConfig:
    description: str
    sample_rate: int
    channels: int
    device: Any = None
    extra_settings: Any = None


def _input_configs(sd: Any) -> list[_InputConfig]:
    """Capture paths to try, best first."""
    configs: list[_InputConfig] = []
    if os.getenv("AUDIO_INPUT", "auto").lower() != "legacy":
        try:
            apis = sd.query_hostapis()
            wasapi = next(i for i, api in enumerate(apis) if "WASAPI" in api["name"])
            device = int(os.getenv("AUDIO_INPUT_DEVICE") or apis[wasapi]["default_input_device"])
            if device >= 0:
                rate = int(sd.query_devices(device)["default_samplerate"])
                configs.append(
                    _InputConfig(
                        f"WASAPI exclusive, raw {rate} Hz",
                        rate,
                        1,
                        device,
                        sd.WasapiSettings(exclusive=True),
                    )
                )
        except Exception:  # noqa: BLE001 - not Windows, or a minimal fake sounddevice
            pass
    configs.append(_InputConfig("default input, 16 kHz", SAMPLE_RATE, CHANNELS))
    return configs


def _to_mono(data: Any) -> np.ndarray:
    """Block from the audio callback -> mono float32 in int16 units."""
    samples = np.asarray(data)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    return samples.astype(np.float32)


def _resample(samples: np.ndarray, rate: int) -> np.ndarray:
    if rate == SAMPLE_RATE or samples.size == 0:
        return samples
    try:
        from scipy.signal import resample_poly

        divisor = math.gcd(rate, SAMPLE_RATE)
        return resample_poly(samples, SAMPLE_RATE // divisor, rate // divisor).astype(np.float32)
    except ImportError:
        if rate % SAMPLE_RATE == 0:  # e.g. 48 kHz: average groups of 3 (box filter)
            factor = rate // SAMPLE_RATE
            usable = samples.size // factor * factor
            return samples[:usable].reshape(-1, factor).mean(axis=1)
        positions = np.linspace(0, samples.size - 1, int(samples.size * SAMPLE_RATE / rate))
        return np.interp(positions, np.arange(samples.size), samples).astype(np.float32)


def _normalise(samples: np.ndarray) -> np.ndarray:
    """Bring quiet recordings to a consistent level without amplifying pure room noise."""
    if samples.size == 0:
        return samples
    loud = float(np.percentile(np.abs(samples), 99.5))
    if loud < 50:  # essentially silence
        return samples
    gain = min(TARGET_PEAK * 32767.0 / loud, MAX_GAIN)
    return samples * gain


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
    global last_input_description

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

    blocks: Queue[np.ndarray] = Queue()
    stop_event = threading.Event()

    def callback(indata: Any, frames: int, callback_time: Any, status: Any) -> None:
        del frames, callback_time
        if status:
            print(f"Audio input warning: {status}")
        blocks.put(_to_mono(np.array(indata, copy=True)))

    def wait_for_manual_stop() -> None:
        try:
            input("Recording... press Enter to stop.")
        except EOFError:
            # Non-interactive environments rely on silence or max_seconds.
            return
        stop_event.set()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Open the best capture path that works on this machine.
    stack = ExitStack()
    chosen: _InputConfig | None = None
    last_error: Exception | None = None
    for config in _input_configs(sd):
        try:
            stream = sd.InputStream(
                device=config.device,
                samplerate=config.sample_rate,
                channels=config.channels,
                dtype="int16",
                blocksize=int(round(config.sample_rate * BLOCK_SECONDS)),
                callback=callback,
                extra_settings=config.extra_settings,
            )
            stack.enter_context(stream)
            chosen = config
            break
        except Exception as exc:  # noqa: BLE001 - PortAudio errors vary; try the next path
            stack.close()
            stack = ExitStack()
            last_error = exc
            print(f"Audio input '{config.description}' unavailable ({exc}); trying the next option")
    if chosen is None:
        raise RuntimeError(f"Unable to access the microphone: {last_error}") from last_error
    last_input_description = chosen.description
    print(f"Recording from: {chosen.description}")

    captured: list[np.ndarray] = []
    speech_detected = False
    total_samples = 0
    first_speech_block = -1
    last_loud_block = -1
    last_data_at = time.monotonic()
    stop_thread: threading.Thread | None = None
    # A fixed threshold fails on noisy microphones (a laptop mic can sit above it all the time, so a
    # pause is never detected), and a one-off measurement at the start fails when the speaker begins
    # talking straight away. So track the room noise continuously: the quietest fifth of everything
    # heard so far (capped, so a long opening sentence cannot push the floor up to speech level).
    threshold = float(RMS_THRESHOLD)
    levels: list[float] = []
    loud_blocks = 0
    speech_blocks = 0
    min_blocks_before_decision = max(1, int(round(CALIBRATION_SECONDS / BLOCK_SECONDS)))
    # Pause detection counts audio blocks, not wall-clock time, and tolerates stray clicks or fan noise.
    block_frames = int(round(chosen.sample_rate * BLOCK_SECONDS))
    window_blocks = max(1, int(SILENCE_SECONDS * chosen.sample_rate / block_frames))
    recent_quiet: deque[bool] = deque(maxlen=window_blocks)

    try:
        with stack:
            if interactive:
                stop_thread = threading.Thread(
                    target=wait_for_manual_stop,
                    name="audio-stop-listener",
                    daemon=True,
                )
                stop_thread.start()

            while not stop_event.is_set():
                if total_samples >= max_seconds * chosen.sample_rate:
                    break
                try:
                    block = blocks.get(timeout=0.1)
                except Empty:
                    if time.monotonic() - last_data_at > 5.0:  # the device stopped delivering audio
                        break
                    continue
                last_data_at = time.monotonic()

                captured.append(block)
                total_samples += block.size
                level = float(np.sqrt(np.mean(np.square(block)))) if block.size else 0.0
                levels.append(level)
                if len(levels) < min_blocks_before_decision:
                    continue
                noise_floor = min(float(np.percentile(levels, NOISE_PERCENTILE)), NOISE_FLOOR_CAP)
                threshold = min(max(RMS_THRESHOLD, noise_floor * NOISE_MARGIN), MAX_RMS_THRESHOLD)
                if level >= threshold:
                    speech_blocks += 1
                    loud_blocks += 1
                    last_loud_block = len(captured) - 1
                    if speech_blocks >= MIN_SPEECH_BLOCKS:
                        if not speech_detected:
                            first_speech_block = len(captured) - MIN_SPEECH_BLOCKS
                        speech_detected = True
                else:
                    speech_blocks = 0
                if speech_detected and loud_blocks >= MIN_LOUD_BLOCKS:
                    quiet_limit = max(threshold * QUIET_RATIO, noise_floor * 1.5)
                    recent_quiet.append(level < quiet_limit)
                    if len(recent_quiet) == window_blocks and sum(recent_quiet) >= QUIET_FRACTION * window_blocks:
                        break
    except OSError as exc:
        raise RuntimeError(f"Unable to access the microphone: {exc}") from exc

    if not captured:
        raise RuntimeError("No audio was captured from the microphone")

    if speech_detected and first_speech_block >= 0:
        # Whisper-tiny hallucinates on long stretches of room noise: keep the speech plus a margin.
        start = max(0, first_speech_block - TRIM_BEFORE_BLOCKS)
        end = min(len(captured), last_loud_block + 1 + TRIM_AFTER_BLOCKS)
        captured = captured[start:end]
    audio = _normalise(_resample(np.concatenate(captured), chosen.sample_rate))
    pcm = np.clip(audio, -32768, 32767).astype("<i2")

    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())

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
