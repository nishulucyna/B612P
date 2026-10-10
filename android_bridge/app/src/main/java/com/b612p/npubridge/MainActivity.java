package com.b612p.npubridge;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Starts the bridge service and shows its status. Keep this screen open during the demo.
 * The banner is red whenever the encoder is not running on the NPU (CPU fallback or load failure).
 */
public class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView banner;
    private TextView details;
    private int lastState = -1;

    private final Runnable refresh = new Runnable() {
        @Override
        public void run() {
            int state = BridgeService.state();
            banner.setText(BridgeService.banner());
            banner.setBackgroundColor(state == BridgeService.STATE_ALERT ? Color.rgb(176, 0, 32)
                    : state == BridgeService.STATE_OK ? Color.rgb(27, 120, 55)
                    : Color.rgb(179, 122, 0));
            details.setText(BridgeService.statusLine());
            if (state != lastState && state == BridgeService.STATE_ALERT) {
                Toast.makeText(MainActivity.this, banner.getText(), Toast.LENGTH_LONG).show();
            }
            lastState = state;
            handler.postDelayed(this, 1000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);

        banner = new TextView(this);
        banner.setPadding(32, 40, 32, 40);
        banner.setTextSize(20);
        banner.setTextColor(Color.WHITE);
        root.addView(banner);

        details = new TextView(this);
        details.setPadding(32, 32, 32, 32);
        details.setTextSize(15);
        root.addView(details);

        setContentView(root);

        Intent service = new Intent(this, BridgeService.class);
        service.putExtra(BridgeService.EXTRA_ALLOW_CPU_FALLBACK,
                getIntent().getBooleanExtra(BridgeService.EXTRA_ALLOW_CPU_FALLBACK, false));
        startService(service);
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
