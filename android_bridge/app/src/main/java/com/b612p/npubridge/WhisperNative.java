package com.b612p.npubridge;

import android.content.res.AssetManager;

/**
 * JNI surface of libASR.so (SNPE encoder on the Hexagon DSP, mel preprocessing, token to text).
 * Method names must match the Java_com_b612p_npubridge_WhisperNative_* functions in
 * app/src/main/cpp/native-lib_pre_post.cpp.
 */
final class WhisperNative {
    static {
        System.loadLibrary("ASR");
    }

    /**
     * Dev switch, default false. When false the encoder must build on the DSP/HTP and InitSnpe
     * returns "ERROR: ..." if it cannot. When true it may build on the CPU and InitSnpe returns
     * "WARN: CPU FALLBACK ...".
     */
    native void setAllowCpuFallback(boolean allow);

    /** Builds the SNPE network from the DLC asset. "" = on the DSP, "WARN: ..." = CPU fallback, "ERROR: ..." = failed. */
    native String InitSnpe(AssetManager assets, String nativeLibraryDir, String encoderDlcFile);

    /** Loads mel filters and vocabulary from filters_vocab_gen.bin. Returns "Successfull" on success. */
    native String LoadVocab(AssetManager assets);

    /** Token ids to text. Stops at the end-of-text token (50257). */
    native String Transcribe(AssetManager assets, long[] tokenIds, int length);

    /**
     * Runs mel + the encoder. wavPath must be a 16 kHz 16-bit WAV file when isRecorded is 1.
     * Fills encoderHiddenState (1500 x 384 floats). Returns "" on success, null if the WAV is
     * rejected, otherwise an error text.
     */
    native String loadModelJNI(AssetManager assets, int isRecorded, String wavPath,
                               float[] inputFeatures, float[] encoderHiddenState, String runtime);
}
