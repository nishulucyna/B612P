package com.b612p.npubridge;

/** LLM backend (Llama 3.2 via Genie on the HTP). */
public interface LlmEngine {
    /** True once the model bundle is loaded and the NPU runtime is up. */
    boolean isReady();

    /** Human-readable status for /health and the on-screen log. */
    String status();

    /**
     * True when the model was created with the NPU requested and loaded. NOTE: the SDK gives no direct
     * proof of which processor ran it; confirm with logcat (hexagon / htp / ggml-hex lines).
     */
    boolean onNpu();

    /** Non-null when something needs the operator's attention (no model file, load failure). */
    String warning();

    /** Runs one completion and returns the raw model text. */
    String generate(String prompt) throws Exception;
}
