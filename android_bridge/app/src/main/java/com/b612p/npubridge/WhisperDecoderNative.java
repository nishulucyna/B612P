package com.b612p.npubridge;

/** JNI surface of the SNPE text decoder in libASR.so (cpp/decoder.cpp). */
final class WhisperDecoderNative {
    static {
        System.loadLibrary("ASR");
    }

    /** Loads the decoder DLC on the DSP. "" = ok, "WARN: ..." = CPU fallback, "ERROR: ..." = failed. */
    native String load(String dlcPath, String embedPath, boolean allowCpu);

    /** Greedy decoding. Returns the generated ids (ending with eot when produced), or null on error (see lastError). */
    native int[] decode(float[] hidden, int[] prompt, int eot, int maxNew);

    native String lastError();

    /** Number of token positions the decoder DLC was built with. */
    native int positions();
}
