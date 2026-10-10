import wave
from array import array

from backend import audio_pipeline


class _FakeInputStream:
    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs

    def __enter__(self):
        samples = array("h", [1_000] * (audio_pipeline.SAMPLE_RATE * 3))
        self.callback(samples, len(samples), None, None)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeSoundDevice:
    InputStream = _FakeInputStream


def test_record_audio_writes_three_seconds_of_required_wav(
    monkeypatch, tmp_path
):
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _FakeSoundDevice)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (_ for _ in ()).throw(
            AssertionError("default recording must not read terminal input")
        ),
    )

    output_path = tmp_path / "mic_input.wav"
    result = audio_pipeline.record_audio(str(output_path), max_seconds=3)

    assert result == str(output_path)
    with wave.open(result, "rb") as wav_file:
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnframes() == 16_000 * 3


def test_interactive_recording_uses_terminal_start_and_stop(
    monkeypatch, tmp_path
):
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _FakeSoundDevice)
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            return ""
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)

    result = audio_pipeline.record_audio(
        str(tmp_path / "interactive.wav"),
        max_seconds=3,
        interactive=True,
    )

    assert result.endswith("interactive.wav")
    assert prompts == [
        "Press Enter to start recording...",
        "Recording... press Enter to stop.",
    ]


def test_speak_tts_uses_offline_engine(monkeypatch):
    spoken = []

    class FakeEngine:
        def say(self, text):
            spoken.append(text)

        def runAndWait(self):
            pass

        def stop(self):
            pass

    class FakePyttsx3:
        @staticmethod
        def init():
            return FakeEngine()

    monkeypatch.setitem(__import__("sys").modules, "pyttsx3", FakePyttsx3)

    audio_pipeline.speak_tts(
        "Testing Qualcomm offline audio pipeline. Water leak detected."
    )

    assert spoken == [
        "Testing Qualcomm offline audio pipeline. Water leak detected."
    ]


class _NoisyRoomStream:
    """0.6 s of room noise (RMS 600, above the old fixed threshold of 500), speech, then a pause."""

    def __init__(self, callback, **kwargs):
        self.callback = callback

    def __enter__(self):
        block = audio_pipeline.BLOCK_SIZE
        for level, count in ((600, 6), (4_000, 8), (600, 40)):
            for _ in range(count):
                self.callback(array("h", [level] * block), block, None, None)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _NoisyRoomSoundDevice:
    InputStream = _NoisyRoomStream


def test_recording_stops_after_a_pause_even_in_a_noisy_room(monkeypatch, tmp_path):
    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _NoisyRoomSoundDevice)
    monkeypatch.setattr(audio_pipeline, "SILENCE_SECONDS", 0.0)  # the fake stream is not real time

    result = audio_pipeline.record_audio(str(tmp_path / "noisy.wav"), max_seconds=15)

    with wave.open(result, "rb") as wav_file:
        frames = wav_file.getnframes()
    block = audio_pipeline.BLOCK_SIZE
    # It must stop at the first pause, long before the 40 quiet blocks that were queued.
    assert frames < (6 + 8 + 5) * block
    assert frames >= (6 + 8) * block


def _sentence_stream(speech_rms, noise_rms=70, seed=1):
    """Room noise, then a 'sentence' of five word bursts with 0.3-0.7 s gaps, then a long pause."""
    import random

    rng = random.Random(seed)
    block = audio_pipeline.BLOCK_SIZE

    def blk(rms):
        return array("h", [int(rng.gauss(0, rms)) for _ in range(block)])

    plan = [(noise_rms, 12)]                                  # 1.2 s of room noise
    for burst, gap in ((6, 4), (9, 6), (5, 3), (8, 7), (7, 0)):  # words and the gaps between them
        plan += [(speech_rms, burst), (noise_rms, gap)]
    plan += [(noise_rms, 40)]                                 # the speaker stops
    spoken_end = sum(n for r, n in plan if r == speech_rms or n == 12) + sum(g for _, g in ((6, 4), (9, 6), (5, 3), (8, 7)))
    return plan, blk, spoken_end


def _record_plan(monkeypatch, tmp_path, plan, blk):
    class Stream:
        def __init__(self, callback, **kwargs):
            self.callback = callback

        def __enter__(self):
            for rms, count in plan:
                for _ in range(count):
                    self.callback(blk(rms), audio_pipeline.BLOCK_SIZE, None, None)
            return self

        def __exit__(self, *exc):
            return False

    class SD:
        InputStream = Stream

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", SD)
    path = audio_pipeline.record_audio(str(tmp_path / "s.wav"), max_seconds=30)
    with wave.open(path, "rb") as wav_file:
        return wav_file.getnframes() / 16_000


def test_pause_ends_recording_but_gaps_between_words_do_not(monkeypatch, tmp_path):
    for speech_rms in (1500, 600, 250):  # strong, normal and faint speech over 70 RMS room noise
        plan, blk, _ = _sentence_stream(speech_rms)
        seconds = _record_plan(monkeypatch, tmp_path, plan, blk)
        speech_seconds = (6 + 4 + 9 + 6 + 5 + 3 + 8 + 7 + 7) / 10   # first word to last word, gaps included
        # Whole sentence kept (nothing cut off mid-sentence) ...
        assert seconds >= speech_seconds, (speech_rms, seconds)
        # ... and it stopped at the pause instead of running through the 4 s of silence that follows.
        assert seconds < speech_seconds + 0.5 + 1.2 + 1.0, (speech_rms, seconds)


def test_recording_reports_a_signal_to_noise_estimate(monkeypatch, tmp_path):
    plan, blk, _ = _sentence_stream(1500)            # speech RMS 1500 over room noise RMS 70
    _record_plan(monkeypatch, tmp_path, plan, blk)
    info = audio_pipeline.last_recording
    assert info["speech_detected"] is True
    assert 18 <= info["snr_db"] <= 32                # 20*log10(1500/70) ~ 26.6 dB


def test_recording_without_speech_has_no_snr(monkeypatch, tmp_path):
    def blk(rms):
        return array("h", [int(((i * 7919) % 141) - 70) for i in range(audio_pipeline.BLOCK_SIZE)])

    _record_plan(monkeypatch, tmp_path, [(70, 40)], blk)   # four seconds of room noise only
    info = audio_pipeline.last_recording
    assert info["speech_detected"] is False
    assert info["snr_db"] is None
