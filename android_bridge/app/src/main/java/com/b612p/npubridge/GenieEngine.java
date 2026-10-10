package com.b612p.npubridge;

/**
 * Llama 3.2 on the Hexagon NPU through the Genie API.
 *
 * NOT IMPLEMENTED YET: the native layer (JNI over libGenie, adapted from
 * qidk/GenAI-Solutions/AI-Assistant) needs the V75 Genie bundle and the QAIRT libraries
 * of the same version. Until then this reports not-ready, so the bridge answers 503
 * instead of returning fake output.
 */
public class GenieEngine implements LlmEngine {
    private final ModelLoader models;

    public GenieEngine(ModelLoader models) {
        this.models = models;
    }

    @Override
    public boolean isReady() {
        return false; // TODO: true once the Genie dialog is created
    }

    @Override
    public String status() {
        return "llm: native NPU backend not linked; " + models.describe(models.llamaDir());
    }

    @Override
    public String generate(String prompt) throws Exception {
        throw new IllegalStateException(status());
    }
}
