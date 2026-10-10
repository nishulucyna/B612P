# Building the Whisper-tiny assets for HDK8650 (SM8650, V75) on Windows

Windows-native build, no Docker or WSL. Output files go in `npu_models/whisper/`:
`whisper_tiny_encoder_w8a16.dlc`, `whisper-decoder-tiny.tflite`, `filters_vocab_gen.bin`.

Requirements: QAIRT SDK 2.47.0.260601 extracted to `qairt_sdk/2.47.0.260601`, and Python 3.10
(the SDK's Windows converter only ships 3.10 native modules). `uv` can provide it.

```bash
mkdir whisper_build && cd whisper_build
uv venv --python 3.10 venv
uv pip install --python venv/Scripts/python.exe numpy==1.26.4 onnx==1.16.1 protobuf==4.25.8 pyyaml packaging pydantic aenum mako decorator absl-py attrs jsonschema lxml scipy pandas rich tabulate safetensors psutil six pillow invoke joblib mock pathlib2 typing-extensions tiktoken numba tqdm more-itertools soundfile huggingface_hub pyarrow
uv pip install --python venv/Scripts/python.exe torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
git clone https://github.com/openai/whisper.git && git clone https://github.com/usefulsensors/openai-whisper.git
(cd whisper && git apply ../../qidk/Solutions/NLPSolution3-AutomaticSpeechRecognition-Whisper/Generate_Assets/whisper.patch)
cp ../scripts/whisper_build/*.py . && venv/Scripts/python.exe prep_encoder.py   # whisper_encoder.onnx + calibration inputs + list.txt

SDK=/d/B612P/qairt_sdk/2.47.0.260601; export PYTHONPATH=$SDK/lib/python PATH=$SDK/lib/x86_64-windows-msvc:$PATH
venv/Scripts/python.exe $SDK/bin/x86_64-windows-msvc/snpe-onnx-to-dlc -i whisper_encoder.onnx -d x.1 1,80,3000 -o whisper_tiny_encoder_fp32.dlc
$SDK/bin/x86_64-windows-msvc/snpe-dlc-quant.exe --input_dlc whisper_tiny_encoder_fp32.dlc --input_list list.txt --output_dlc whisper_tiny_encoder_w8a16_unprepared.dlc --weights_bitwidth 8 --act_bitwidth 16
$SDK/bin/x86_64-windows-msvc/snpe-dlc-graph-prepare.exe --input_dlc whisper_tiny_encoder_w8a16_unprepared.dlc --output_dlc whisper_tiny_encoder_w8a16.dlc --htp_socs sm8650
venv/Scripts/python.exe gen_vocab.py                                              # filters_vocab_gen.bin
# decoder: openai-whisper/models/whisper-decoder-tiny.tflite (used as-is)
```

Checks done: FP32 DLC vs PyTorch cosine 1.0; w8a16 vs FP32 cosine 0.994 (host, one clip).
Not yet verified: end-to-end transcription on the board.
Input raw layout is (3000, 80) float32, i.e. the transposed mel, matching the Android app.
Note: in QAIRT 2.47, `snpe-dlc-quantize --enable_htp` is split into `snpe-dlc-quant` + `snpe-dlc-graph-prepare`.

## Whisper-small (better accuracy; encoder AND decoder on the DSP)

On the board, `whisper-small` is used automatically when these three files are in `/data/local/tmp/npu_models/whisper/`
(otherwise the app falls back to the tiny model packaged in the APK):

| file | what | how it is built |
|---|---|---|
| `whisper_small_encoder_w8a16.dlc` (187 MB) | encoder, w8a16, HTP v75 | `export_small_encoder.py small` -> `snpe-onnx-to-dlc -d x.1 1,80,3000` -> `snpe-dlc-quant` -> `snpe-dlc-graph-prepare --htp_socs sm8650` (same as tiny) |
| `whisper_decoder_small_fp16_htp.dlc` (618 MB) | decoder, fp16, HTP v75 | `HALF=1 export_decoder.py small 96` -> `snpe-onnx-to-dlc -d emb 96,768 -d xa 1500,768 -d idx 1 --float_bitwidth 16` -> `snpe-dlc-graph-prepare --htp_socs sm8650` |
| `whisper_small_embed.bin` (80 MB) | positional + token embedding table (fp16) | written by `export_decoder.py` |

Lessons that cost time (all verified against PyTorch on the board with `snpe-net-run --use_dsp`, cosine 0.99999):
* 3-D graph inputs are re-laid-out by the converter; use 2-D inputs for anything that is not the mel (`xa` is `(1500, D)`).
* Token ids must not be graph inputs of an fp16 graph: ids above 2048 are not exact in fp16 (50258 became 50272). The embedding lookup is done on the CPU (`cpp/decoder.cpp`) and the graph takes `emb`.
* The decoder has no KV cache and fixed length L=96 (prompt + up to ~90 new tokens); padding is hidden by the causal mask.
* The laptop has little RAM: the export scripts load only the encoder or decoder weights (`mmap=True`) and the decoder is exported in fp16.
* Measured with `scripts/stt_snr_eval.py` (synthetic speech + white noise, 6 sentences): tiny 12.7/14.1/19.7/18.3% WER and small 9.9/9.9/11.3/12.7% at clean/20/10/5 dB; small takes ~2.0 s per clip vs ~1.0 s.
