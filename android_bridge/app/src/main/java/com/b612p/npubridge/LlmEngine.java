package com.b612p.npubridge;

/** LLM backend (Llama 3.2 via Genie on the HTP). */
public interface LlmEngine {
    /** True once the model bundle is loaded and the NPU runtime is up. */
    boolean isReady();

    /** Human-readable status for /health and the on-screen log. */
    String status();

    /** Runs one completion and returns the raw model text. */
    String generate(String prompt) throws Exception;
}
