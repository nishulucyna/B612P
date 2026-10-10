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
 * Whisper-tiny speech to text.
 *   encoder: quantized w8a16 DLC on the Hexagon DSP/HTP through SNPE (native, libASR.so)
 *   decoder: TFLite on the CPU, greedy decoding, as in the qidk sample
 *
 * The model files are packaged as APK assets (copied in by scripts/copy_whisper_assets.ps1).
 * If any piece fails to load the engine stays not-ready and the bridge answers HTTP 503.
 */
public class WhisperEngine implements SttEngine {
    private static final String TAG = "NpuBridge";

    private static final String DECODER_ASSET = "whisper-decoder-tiny.tflite";
    private static final int N_SAMPLES_FEATURES = 80 * 3000;       // encoder input floats
    private static final int HIDDEN_FRAMES = 1500;
    private static final int HIDDEN_DIM = 384;
    private static final int VOCAB = 51865;
    private static final int EOT = 50257;
    // <|startoftranscript|><|en|><|transcribe|><|notimestamps|>
    private static final long[] PROMPT = {50258, 50259, 50359, 50363};
    private static final int MAX_NEW_TOKENS = 128;

    private final Context context;
    private WhisperNative nativeLib;
    private Interpreter decoder;
    private volatile boolean ready = false;
    private volatile String status = "whisper: not loaded yet";

    public WhisperEngine(Context context) {
        this.context = context.getApplicationContext();
    }

    /** Loads the encoder, vocabulary and decoder. Slow; call off the main thread. */
    public void load() {
        status = "whisper: loading...";
        try {
            nativeLib = new WhisperNative();

            String init = nativeLib.InitSnpe(context.getAssets(), context.getApplicationInfo().nativeLibraryDir);
            if (init == null || !init.isEmpty()) {
                throw new IllegalStateException("encoder not built: " + init);
            }
            String vocab = nativeLib.LoadVocab(context.getAssets());
            if (vocab == null || !vocab.startsWith("Success")) {
                throw new IllegalStateException("vocab not loaded: " + vocab);
            }

            Interpreter.Options options = new Interpreter.Options();
            options.setNumThreads(4);
            decoder = new Interpreter(mapAsset(DECODER_ASSET), options);
            decoder.resizeInput(0, new int[]{1, HIDDEN_FRAMES, HIDDEN_DIM});
            decoder.resizeInput(1, new int[]{1, PROMPT.length});

            ready = true;
            status = "whisper: ready (encoder on DSP via SNPE, decoder on TFLite CPU)";
            Log.i(TAG, status);
        } catch (Throwable t) {
            ready = false;
            status = "whisper: load failed: " + t;
            Log.e(TAG, status, t);
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
            float[] hiddenFlat = new float[HIDDEN_FRAMES * HIDDEN_DIM];
            String result = nativeLib.loadModelJNI(context.getAssets(), 1, wav.getAbsolutePath(),
                    features, hiddenFlat, "DSP");
            if (result == null) {
                throw new IllegalArgumentException("audio rejected: need a 16 kHz, 16-bit, mono or stereo WAV");
            }
            if (!result.isEmpty()) {
                throw new IllegalStateException("encoder failed: " + result);
            }

            float[][][] hidden = new float[1][HIDDEN_FRAMES][HIDDEN_DIM];
            int idx = 0;
            for (int j = 0; j < HIDDEN_FRAMES; j++) {
                for (int k = 0; k < HIDDEN_DIM; k++) {
                    hidden[0][j][k] = hiddenFlat[idx++];
                }
            }
            return decode(hidden);
        } finally {
            //noinspection ResultOfMethodCallIgnored
            wav.delete();
        }
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
