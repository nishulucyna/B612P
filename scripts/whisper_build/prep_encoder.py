"""Export Whisper-tiny encoder to ONNX and write calibration inputs (mirrors whisper_notebook.ipynb)."""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper"))
import numpy as np, torch, soundfile as sf
import whisper
from whisper.audio import log_mel_spectrogram, pad_or_trim

here = os.path.dirname(os.path.abspath(__file__))
model = whisper.load_model("tiny", device="cpu")          # downloads tiny.pt once (public)
model.eval()
enc = model.encoder
try:
    torch.onnx.export(enc, torch.randn(1, 80, 3000), os.path.join(here, "whisper_encoder.onnx"),
                      input_names=["x.1"], opset_version=14, dynamo=False)
except TypeError:
    torch.onnx.export(enc, torch.randn(1, 80, 3000), os.path.join(here, "whisper_encoder.onnx"),
                      input_names=["x.1"], opset_version=14)
print("exported encoder onnx")

# calibration audio: public HF test dataset (same as the notebook)
from huggingface_hub import snapshot_download
import pyarrow.parquet as pq
d = snapshot_download("hf-internal-testing/librispeech_asr_dummy", repo_type="dataset")
files = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith(".parquet")]
print("parquet:", files)
rows = pq.read_table(files[0]).to_pylist()
out = os.path.join(here, "input_features"); os.makedirs(out, exist_ok=True)
lst = []
for i, row in enumerate(rows[:25]):
    audio, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
    assert sr == 16000, sr
    mel = log_mel_spectrogram(pad_or_trim(torch.from_numpy(audio)), 80).numpy()   # (80, 3000)
    raw = os.path.join(out, f"inp_val_{i}.raw")
    mel.T.astype(np.float32).tofile(raw)                                          # (3000, 80), as the app feeds it
    lst.append(raw)
open(os.path.join(here, "list.txt"), "w").write("\n".join(lst) + "\n")
print("calibration samples:", len(lst))
