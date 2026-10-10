package com.b612p.npubridge;

/**
 * Whisper STT on the Hexagon NPU/DSP.
 *
 * NOT IMPLEMENTED YET: the native inference layer (JNI over SNPE/QAIRT, adapted from
 * qidk/Solutions/NLPSolution3-AutomaticSpeechRecognition-Whisper/Android_App_Whisper)
 * needs the V75 model files and the QAIRT libraries. Until then this reports not-ready
 * so the bridge answers 503 and the orchestrator falls back to its mock. It never
 * returns made-up text.
 */
public class WhisperEngine implements SttEngine {
    private final ModelLoader models;

    public WhisperEngine(ModelLoader models) {
        this.models = models;
    }

    @Override
    public boolean isReady() {
        return false; // TODO: true once the native Whisper pipeline is loaded
    }

    @Override
    public String status() {
        return "whisper: native NPU backend not linked; " + models.describe(models.whisperDir());
    }

    @Override
    public String transcribe(byte[] wavBytes) throws Exception {
        throw new IllegalStateException(status());
    }
}
