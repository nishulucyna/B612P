"""Export a Whisper encoder (size from argv[1]) to ONNX using only the encoder weights (memory-mapped; the laptop is RAM-poor)."""
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "whisper"))
import torch
from whisper.model import AudioEncoder, ModelDimensions
size = sys.argv[1] if len(sys.argv) > 1 else "small"
ckpt = torch.load(os.path.expanduser(f"~/.cache/whisper/{size}.pt"), map_location="cpu", mmap=True, weights_only=True)
d = ckpt["dims"]
enc = AudioEncoder(d["n_mels"], d["n_audio_ctx"], d["n_audio_state"], d["n_audio_head"], d["n_audio_layer"])
enc.load_state_dict({k[len("encoder."):]: v for k, v in ckpt["model_state_dict"].items() if k.startswith("encoder.")})
enc.eval()
out = os.path.join(here, f"whisper_encoder_{size}.onnx")
with torch.no_grad():
    try:
        torch.onnx.export(enc, torch.randn(1, 80, 3000), out, input_names=["x.1"], opset_version=14, dynamo=False, do_constant_folding=False)
    except TypeError:
        torch.onnx.export(enc, torch.randn(1, 80, 3000), out, input_names=["x.1"], opset_version=14, do_constant_folding=False)
print("exported", out, d)
