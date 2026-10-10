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
