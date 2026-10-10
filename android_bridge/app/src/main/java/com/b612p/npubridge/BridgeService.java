package com.b612p.npubridge;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;

import java.io.IOException;

/** Owns the HTTP server and the engines. Started by MainActivity. */
public class BridgeService extends Service {
    private static final String TAG = "NpuBridge";

    private static volatile BridgeServer server;
    private static volatile SttEngine stt;
    private static volatile LlmEngine llm;

    public static final String EXTRA_ALLOW_CPU_FALLBACK = "allow_cpu_fallback";

    /** The engines, for the on-device UI to call directly (null until the service has started). */
    public static SttEngine sttEngine() {
        return stt;
    }

    public static LlmEngine llmEngine() {
        return llm;
    }

    public static final int STATE_LOADING = 0;
    public static final int STATE_OK = 1;
    public static final int STATE_ALERT = 2;

    /** Operator-facing state: loading (amber), running on the NPU (green), problem or CPU fallback (red). */
    public static int state() {
        SttEngine s = stt;
        LlmEngine l = llm;
        if (s == null || l == null) {
            return STATE_LOADING;
        }
        if (s.warning() != null || l.warning() != null) {
            return STATE_ALERT;
        }
        return (s.isReady() && s.onNpu() && l.isReady() && l.onNpu()) ? STATE_OK : STATE_LOADING;
    }

    /** One-line banner text for the current state. */
    public static String banner() {
        SttEngine s = stt;
        LlmEngine l = llm;
        switch (state()) {
            case STATE_ALERT:
                StringBuilder sb = new StringBuilder("PROBLEM - not fully on the NPU:");
                if (s.warning() != null) {
                    sb.append("\nSTT: ").append(s.warning());
                }
                if (l.warning() != null) {
                    sb.append("\nLLM: ").append(l.warning());
                }
                return sb.toString();
            case STATE_OK:
                return "STT encoder on the NPU (DSP); LLM loaded with the NPU requested - confirm in logcat";
            default:
                return "Loading models...";
        }
    }

    /** Status text for the on-screen view. */
    public static String statusLine() {
        if (server == null) {
            return "server not running";
        }
        return "listening on 127.0.0.1:" + BridgeServer.PORT
                + "\n" + stt.status()
                + "\n" + llm.status();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (server == null) {
            ModelLoader models = new ModelLoader();
            // Dev switch, off by default: `am start -n com.b612p.npubridge/.MainActivity --ez allow_cpu_fallback true`
            boolean allowCpu = intent != null && intent.getBooleanExtra(EXTRA_ALLOW_CPU_FALLBACK, false);
            final WhisperEngine whisper = new WhisperEngine(this, allowCpu);
            final GenieEngine genie = new GenieEngine(this, allowCpu);
            stt = whisper;
            llm = genie;
            // Model loading takes a while; keep the HTTP server (and /health) responsive meanwhile.
            // One thread, one model at a time, to keep peak memory down.
            new Thread(new Runnable() {
                @Override
                public void run() {
                    whisper.load();
                    genie.load();
                }
            }, "model-load").start();
            BridgeServer s = new BridgeServer(stt, llm);
            try {
                s.start(SOCKET_READ_TIMEOUT_MS, false);
                server = s;
                Log.i(TAG, "bridge started on port " + BridgeServer.PORT);
            } catch (IOException e) {
                Log.e(TAG, "could not start server", e);
            }
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        BridgeServer s = server;
        if (s != null) {
            s.stop();
            server = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // NanoHTTPD's read timeout (ms) covers receiving the request, not inference time.
    private static final int SOCKET_READ_TIMEOUT_MS = 30_000;
}
