package com.b612p.npubridge;

/** Speech-to-text backend (Whisper: encoder on the HTP/DSP, decoder TFLite). */
public interface SttEngine {
    /** True once the models are loaded and the NPU runtime is up. */
    boolean isReady();

    /** Human-readable status for /health and the on-screen log. */
    String status();

    /** True only when inference really runs on the NPU/DSP. False while loading or on any fallback. */
    boolean onNpu();

    /** Non-null when something needs the operator's attention (CPU fallback, load failure). */
    String warning();

    /** Transcribes a 16 kHz mono 16-bit PCM WAV file given as raw bytes. */
    String transcribe(byte[] wavBytes) throws Exception;
}
