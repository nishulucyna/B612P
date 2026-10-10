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
