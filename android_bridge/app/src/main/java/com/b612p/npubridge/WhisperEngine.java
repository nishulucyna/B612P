package com.b612p.npubridge;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.util.Log;

import org.tensorflow.lite.Interpreter;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

/**
 * Whisper speech to text.
 *   tiny  (packaged in the APK): encoder w8a16 DLC on the DSP through SNPE, decoder TFLite on the CPU (qidk sample)
 *   small (pushed to /data/local/tmp/npu_models/whisper/ when present): encoder w8a16 DLC and fp16 decoder DLC, both on the DSP
 *
 * The model files are packaged as APK assets (copied in by scripts/copy_whisper_assets.ps1).
 * If any piece fails to load the engine stays not-ready and the bridge answers HTTP 503.
 */
public class WhisperEngine implements SttEngine {
    private static final String TAG = "NpuBridge";

    private static final String DECODER_ASSET = "whisper-decoder-tiny.tflite";
    private static final int N_SAMPLES_FEATURES = 80 * 3000;       // encoder input floats
    private static final int HIDDEN_FRAMES = 1500;
    private static final int TINY_DIM = 384;
    private static final int SMALL_DIM = 768;
    static final String SMALL_ENCODER = "whisper_small_encoder_w8a16.dlc";
    static final String SMALL_EMBED = "whisper_small_embed.bin";
    static final String SMALL_DECODER = "whisper_decoder_small_fp16_htp.dlc";
    private static final int VOCAB = 51865;
    private static final int EOT = 50257;
    // <|startoftranscript|><|en|><|transcribe|><|notimestamps|>
    private static final long[] PROMPT = {50258, 50259, 50359, 50363};
    private static final int MAX_NEW_TOKENS = 128;

    private final Context context;
    private WhisperNative nativeLib;
    private Interpreter decoder;
    private WhisperDecoderNative npuDecoder;       // set in small mode
    private int hiddenDim = TINY_DIM;
    private volatile boolean ready = false;
    private volatile boolean onNpu = false;
    private volatile String warning = null;
    private volatile String status = "whisper: not loaded yet";
    private final boolean allowCpuFallback;

    /** @param allowCpuFallback dev-only; when false the engine refuses to run unless the encoder is on the DSP */
    public WhisperEngine(Context context, boolean allowCpuFallback) {
        this.context = context.getApplicationContext();
        this.allowCpuFallback = allowCpuFallback;
    }

    /** Loads the encoder, vocabulary and decoder. Slow; call off the main thread. */
    public void load() {
        status = "whisper: loading...";
        try {
            nativeLib = new WhisperNative();
            nativeLib.setAllowCpuFallback(allowCpuFallback);

            File dir = new File(ModelLoader.DEFAULT_ROOT, "whisper");
            File smallEnc = new File(dir, SMALL_ENCODER);
            File smallDec = new File(dir, SMALL_DECODER);
            boolean small = smallEnc.isFile() && smallDec.isFile() && new File(dir, SMALL_EMBED).isFile();
            hiddenDim = small ? SMALL_DIM : TINY_DIM;

            String init = nativeLib.InitSnpe(context.getAssets(), context.getApplicationInfo().nativeLibraryDir,
                    small ? smallEnc.getAbsolutePath() : "");
            boolean cpuFallback = false;
            if (init == null || init.startsWith("ERROR") || (!init.isEmpty() && !init.startsWith("WARN"))) {
                throw new IllegalStateException(init == null ? "encoder not built" : init);
            }
            if (init.startsWith("WARN")) {
                cpuFallback = true;
                warning = init;
                Log.e(TAG, "NPU_ALERT: " + init);
            }
            String vocab = nativeLib.LoadVocab(context.getAssets());
            if (vocab == null || !vocab.startsWith("Success")) {
                throw new IllegalStateException("vocab not loaded: " + vocab);
            }

            String decoderWhere;
            if (small) {
                npuDecoder = new WhisperDecoderNative();
                String d = npuDecoder.load(smallDec.getAbsolutePath(), new File(dir, SMALL_EMBED).getAbsolutePath(), allowCpuFallback);
                if (d == null || d.startsWith("ERROR")) {
                    throw new IllegalStateException(d == null ? "decoder not built" : d);
                }
                if (d.startsWith("WARN")) {
                    cpuFallback = true;
                    warning = warning == null ? d : warning + "; " + d;
                    Log.e(TAG, "NPU_ALERT: " + d);
                }
                decoderWhere = "decoder on DSP via SNPE";
            } else {
                Interpreter.Options options = new Interpreter.Options();
                options.setNumThreads(4);
                decoder = new Interpreter(mapAsset(DECODER_ASSET), options);
                decoder.resizeInput(0, new int[]{1, HIDDEN_FRAMES, hiddenDim});
                decoder.resizeInput(1, new int[]{1, PROMPT.length});
                decoderWhere = "decoder on TFLite CPU";
            }

            onNpu = !cpuFallback;
            ready = true;
            status = cpuFallback
                    ? "whisper: READY BUT ON CPU, NOT THE NPU (fallback allowed)"
                    : "whisper-" + (small ? "small" : "tiny") + ": ready (encoder on DSP via SNPE, " + decoderWhere + ")";
            Log.i(TAG, status);
        } catch (Throwable t) {
            ready = false;
            onNpu = false;
            warning = String.valueOf(t.getMessage() != null ? t.getMessage() : t);
            status = "whisper: load failed: " + warning;
            Log.e(TAG, "NPU_ALERT: " + status, t);
        }
    }

    @Override
    public boolean isReady() {
        return ready;
    }

    @Override
    public String status() {
        return status;
    }

    @Override
    public boolean onNpu() {
        return onNpu;
    }

    @Override
    public String warning() {
        return warning;
    }

    @Override
    public String transcribe(byte[] wavBytes) throws Exception {
        if (!ready) {
            throw new IllegalStateException(status);
        }
        File wav = File.createTempFile("stt", ".wav", context.getCacheDir());
        try {
            try (FileOutputStream out = new FileOutputStream(wav)) {
                out.write(wavBytes);
            }

            float[] features = new float[N_SAMPLES_FEATURES];
            float[] hiddenFlat = new float[HIDDEN_FRAMES * hiddenDim];
            String result = nativeLib.loadModelJNI(context.getAssets(), 1, wav.getAbsolutePath(),
                    features, hiddenFlat, "DSP");
            if (result == null) {
                throw new IllegalArgumentException("audio rejected: need a 16 kHz, 16-bit, mono or stereo WAV");
            }
            if (!result.isEmpty()) {
                throw new IllegalStateException("encoder failed: " + result);
            }

            if (npuDecoder != null) {
                return decodeOnNpu(hiddenFlat);
            }
            float[][][] hidden = new float[1][HIDDEN_FRAMES][hiddenDim];
            int idx = 0;
            for (int j = 0; j < HIDDEN_FRAMES; j++) {
                for (int k = 0; k < hiddenDim; k++) {
                    hidden[0][j][k] = hiddenFlat[idx++];
                }
            }
            return decode(hidden);
        } finally {
            //noinspection ResultOfMethodCallIgnored
            wav.delete();
        }
    }

    /** Greedy decoding on the DSP (the decoder DLC has fixed positions and no KV cache). */
    private String decodeOnNpu(float[] hiddenFlat) {
        int[] prompt = new int[PROMPT.length];
        for (int i = 0; i < prompt.length; i++) {
            prompt[i] = (int) PROMPT[i];
        }
        int[] gen = npuDecoder.decode(hiddenFlat, prompt, EOT, Math.min(MAX_NEW_TOKENS, npuDecoder.positions() - prompt.length - 1));
        if (gen == null) {
            throw new IllegalStateException("decoder failed: " + npuDecoder.lastError());
        }
        int n = gen.length;
        long[] textIds = new long[n + (n > 0 && gen[n - 1] == EOT ? 0 : 1)];
        for (int i = 0; i < n; i++) {
            textIds[i] = gen[i];
        }
        if (textIds.length != n) {
            textIds[n] = EOT;                                    // hit the cap: terminate so no token is dropped
        }
        String text = nativeLib.Transcribe(context.getAssets(), textIds, textIds.length);
        return text == null ? "" : text.trim();
    }

    /** Greedy decoding (the TFLite decoder has no KV cache, so each step re-runs the prefix). */
    private String decode(float[][][] hidden) {
        long[] ids = PROMPT.clone();
        for (int step = 0; step < MAX_NEW_TOKENS; step++) {
            float[][][] logits = new float[1][ids.length][VOCAB];
            Map<Integer, Object> outputs = new HashMap<>();
            outputs.put(0, logits);
            decoder.runForMultipleInputsOutputs(new Object[]{hidden, new long[][]{ids}}, outputs);

            int next = argMax(logits[0][ids.length - 1]);
            ids = Arrays.copyOf(ids, ids.length + 1);
            ids[ids.length - 1] = next;
            if (next == EOT) {
                break;
            }
        }
        if (ids[ids.length - 1] != EOT) {
            ids = Arrays.copyOf(ids, ids.length + 1);   // hit the cap: terminate so no token is dropped
            ids[ids.length - 1] = EOT;
        }
        long[] textIds = Arrays.copyOfRange(ids, PROMPT.length, ids.length);
        String text = nativeLib.Transcribe(context.getAssets(), textIds, textIds.length);
        return text == null ? "" : text.trim();
    }

    private static int argMax(float[] a) {
        int best = 0;
        for (int i = 1; i < a.length; i++) {
            if (a[i] > a[best]) {
                best = i;
            }
        }
        return best;
    }

    private MappedByteBuffer mapAsset(String name) throws IOException {
        try (AssetFileDescriptor fd = context.getAssets().openFd(name);
             FileInputStream in = new FileInputStream(fd.getFileDescriptor())) {
            return in.getChannel().map(FileChannel.MapMode.READ_ONLY, fd.getStartOffset(), fd.getDeclaredLength());
        }
    }
}
