package com.huawei.aifttr.digitalpersonshell.ui;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;

/**
 * 极简启动载体（真机集成验证用）。
 * <p>
 * 运行期申请 RECORD_AUDIO，随后启动 {@link VoiceForegroundService} 并 self finish。
 * 不引入 UI 框架；仅用于触发前台唤醒服务。
 */
public class LaunchActivity extends Activity {


    private static final int REQ_RECORD_AUDIO = 0x01;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(
                    new String[]{Manifest.permission.RECORD_AUDIO}, REQ_RECORD_AUDIO);
        } else {
            startVoiceService();
            finish();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        startVoiceService();
        finish();
    }

    private void startVoiceService() {
        Intent intent = new Intent(this, VoiceForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }
}
