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
            final WhisperEngine whisper = new WhisperEngine(this);
            stt = whisper;
            llm = new GenieEngine(models);
            // Model loading takes a while; keep the HTTP server (and /health) responsive meanwhile.
            new Thread(new Runnable() {
                @Override
                public void run() {
                    whisper.load();
                }
            }, "whisper-load").start();
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
