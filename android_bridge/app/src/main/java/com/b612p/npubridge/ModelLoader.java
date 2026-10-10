package com.b612p.npubridge;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Locates model files pushed over USB, e.g.
 *   adb push npu_models /data/local/tmp/npu_models
 *
 * Expected layout (file names inside each folder are filled in once the AI Hub
 * artifacts for SM8650 / V75 are downloaded):
 *   /data/local/tmp/npu_models/whisper/   Whisper encoder + decoder + vocab
 *   /data/local/tmp/npu_models/llama/     Genie bundle (config json, context bins, tokenizer)
 *
 * The app needs read access to that path; setup_hdk.sh sets SELinux permissive for this.
 */
public final class ModelLoader {
    public static final String DEFAULT_ROOT = "/data/local/tmp/npu_models";

    private final File root;

    public ModelLoader() {
        this(new File(DEFAULT_ROOT));
    }

    public ModelLoader(File root) {
        this.root = root;
    }

    public File whisperDir() {
        return new File(root, "whisper");
    }

    public File llamaDir() {
        return new File(root, "llama");
    }

    /** Names of the files in a model folder, or an empty list if it is missing/unreadable. */
    public List<String> list(File dir) {
        String[] names = dir.list();
        if (names == null) {
            return new ArrayList<>();
        }
        Arrays.sort(names);
        return new ArrayList<>(Arrays.asList(names));
    }

    /** One-line summary used in status text. */
    public String describe(File dir) {
        if (!dir.isDirectory()) {
            return dir.getPath() + " missing (adb push the models first)";
        }
        List<String> files = list(dir);
        return files.isEmpty()
                ? dir.getPath() + " is empty or unreadable"
                : dir.getPath() + ": " + files.size() + " files";
    }
}
