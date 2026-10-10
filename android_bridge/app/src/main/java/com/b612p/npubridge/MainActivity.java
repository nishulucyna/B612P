package com.b612p.npubridge;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.WindowManager;
import android.widget.TextView;

/** Starts the bridge service and shows its status. Keep this screen open during the demo. */
public class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView view;

    private final Runnable refresh = new Runnable() {
        @Override
        public void run() {
            view.setText("NPU bridge\n\n" + BridgeService.statusLine());
            handler.postDelayed(this, 2000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        view = new TextView(this);
        view.setPadding(32, 32, 32, 32);
        view.setTextSize(16);
        setContentView(view);
        startService(new Intent(this, BridgeService.class));
    }

    @Override
    protected void onResume() {
        super.onResume();
        handler.post(refresh);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(refresh);
        super.onPause();
    }
}
