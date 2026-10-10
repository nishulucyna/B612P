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
        lambda prompt: "" if prompt.endswith("...") else (_ for _ in ()).throw(EOFError),
    )

    output_path = tmp_path / "mic_input.wav"
    result = audio_pipeline.record_audio(str(output_path), max_seconds=3)

    assert result == str(output_path)
    with wave.open(result, "rb") as wav_file:
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnframes() == 16_000 * 3


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
