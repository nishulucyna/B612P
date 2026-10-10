"""Export a Whisper text decoder to ONNX with fixed shapes so it can run as an SNPE DLC on the HTP.
Inputs : emb   float (L, D)    token embedding + positional embedding of the padded ids, computed on the CPU. Token ids cannot
                               be graph inputs: the fp16 graph cannot hold integers above 2048 exactly (50258 would become 50272).
         xa    float (1500, D) encoder output (2D so the converter does not reinterpret the layout)
         idx   float (1,)      position whose next-token logits we want (< 96, exact in fp16)
Output : logits float (1, V)
No KV cache: every step re-runs the L positions (padding is hidden by the causal mask).
Also writes whisper_<size>_embed.bin = positional embedding (L x D fp16) followed by the token table (V x D fp16)."""
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "whisper"))
import numpy as np, torch
from whisper.model import TextDecoder
size = sys.argv[1] if len(sys.argv) > 1 else "small"
L = int(sys.argv[2]) if len(sys.argv) > 2 else 96
ckpt = torch.load(os.path.expanduser(f"~/.cache/whisper/{size}.pt"), map_location="cpu", mmap=True, weights_only=True)
d = ckpt["dims"]
dec = TextDecoder(d["n_vocab"], d["n_text_ctx"], d["n_text_state"], d["n_text_head"], d["n_text_layer"])
dec.load_state_dict({k[len("decoder."):]: v for k, v in ckpt["model_state_dict"].items() if k.startswith("decoder.")})
dec.eval()

pos = dec.positional_embedding[:L].detach().numpy().astype(np.float16)
tab = dec.token_embedding.weight.detach().numpy().astype(np.float16)
with open(os.path.join(here, f"whisper_{size}_embed.bin"), "wb") as f:
    f.write(pos.tobytes()); f.write(tab.tobytes())
print("embed.bin", pos.shape, tab.shape)

HALF = os.environ.get('HALF', '0') == '1'
if HALF:
    dec.half()
    for m in dec.modules():
        if isinstance(m, torch.nn.LayerNorm): m.float()

class Step(torch.nn.Module):
    def __init__(self, dec):
        super().__init__(); self.dec = dec
    def forward(self, emb, xa, idx):
        xa = xa.unsqueeze(0)
        x = emb.unsqueeze(0)
        for b in self.dec.blocks:
            x = b(x, xa, mask=self.dec.mask[:L, :L])
        x = self.dec.ln(x)
        x = torch.index_select(x, 1, idx.round().long())                 # (1,1,D)
        return (x @ self.dec.token_embedding.weight.T)[:, 0, :]

out = os.path.join(here, f"whisper_decoder_{size}_L{L}.onnx")
dt = torch.float16 if HALF else torch.float32
with torch.no_grad():
    args = (torch.zeros(L, d["n_text_state"]).to(dt), torch.randn(1500, d["n_audio_state"]).to(dt), torch.zeros(1))
    torch.onnx.export(Step(dec), args, out, input_names=["emb", "xa", "idx"], output_names=["logits"], opset_version=14,
                      do_constant_folding=False, dynamo=False)
print("exported", out)
