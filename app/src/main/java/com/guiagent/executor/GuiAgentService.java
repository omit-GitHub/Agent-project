package com.guiagent.executor;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Path;
import android.os.Bundle;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * 无障碍服务:系统在「设置→无障碍」开启后常驻;onServiceConnected 起 WebSocket
 * 服务(:8322),接收 instruction-protocol 指令并翻译为无障碍动作。不依赖 root/adb。
 */
public class GuiAgentService extends AccessibilityService {

    private static final String TAG = "guiagent";
    private static volatile GuiAgentService instance;

    private WsCommandServer server;

    public static GuiAgentService get() {
        return instance;
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        // 运行时强制置位关键 flag:FLAG_REPORT_VIEW_IDS 决定能否取 resource-id
        AccessibilityServiceInfo info = getServiceInfo();
        if (info != null) {
            info.flags |= AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                    | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;
            setServiceInfo(info);
        }
        if (server != null) {
            server.stop();
            server = null;
        }
        server = new WsCommandServer(this);
        server.start();
        Log.i(TAG, "service connected, ws server up");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        /* v1 不用事件流 */
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        if (server != null) {
            server.stop();
            server = null;
        }
        if (instance == this) instance = null;
        return super.onUnbind(intent);
    }

    // ---------- 感知 ----------
    public AccessibilityNodeInfo root() {
        return getRootInActiveWindow();
    }

    public List<AccessibilityNodeInfo> findNodes(Match m) {
        return Nodes.find(root(), m);
    }

    // ---------- 节点级动作 ----------
    public boolean click(AccessibilityNodeInfo node) {
        return Nodes.clickableTarget(node).performAction(AccessibilityNodeInfo.ACTION_CLICK);
    }

    public boolean longClick(AccessibilityNodeInfo node) {
        return Nodes.clickableTarget(node).performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK);
    }

    public boolean setText(AccessibilityNodeInfo node, CharSequence text) {
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
    }

    /** 聚焦 -> 写剪贴板 -> ACTION_PASTE。set_text 被拒收时降级用。 */
    public boolean paste(AccessibilityNodeInfo node, CharSequence text) {
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("guiagent", text));
        return node.performAction(AccessibilityNodeInfo.ACTION_PASTE);
    }

    public boolean scroll(AccessibilityNodeInfo node, int actionId) {
        return node.performAction(actionId);
    }

    // ---------- 坐标级动作(dispatchGesture, API24+) ----------
    public boolean gesture(List<float[]> points, long durationMs) {
        if (points == null || points.isEmpty()) return false;
        Path path = new Path();
        path.moveTo(points.get(0)[0], points.get(0)[1]);
        for (int i = 1; i < points.size(); i++) {
            path.lineTo(points.get(i)[0], points.get(i)[1]);
        }
        GestureDescription.StrokeDescription stroke =
                new GestureDescription.StrokeDescription(path, 0L, durationMs);
        GestureDescription gd = new GestureDescription.Builder().addStroke(stroke).build();
        final CountDownLatch latch = new CountDownLatch(1);
        final boolean[] ok = {false};
        dispatchGesture(gd, new GestureResultCallback() {
            @Override
            public void onCompleted(GestureDescription gestureDescription) {
                ok[0] = true;
                latch.countDown();
            }

            @Override
            public void onCancelled(GestureDescription gestureDescription) {
                ok[0] = false;
                latch.countDown();
            }
        }, null);
        try {
            latch.await(durationMs + 2000, TimeUnit.MILLISECONDS);
        } catch (InterruptedException ignored) {
        }
        return ok[0];
    }

    // ---------- 系统级 ----------
    public boolean global(int actionId) {
        return performGlobalAction(actionId);
    }

    /** 拉起指定包的 launcher(或显式 cls)。 */
    public void launch(String pkg, String cls) {
        Intent intent;
        if (cls != null && !cls.isEmpty()) {
            intent = new Intent().setClassName(pkg, cls).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        } else {
            intent = getPackageManager().getLaunchIntentForPackage(pkg);
            if (intent == null) throw new Err("NO_MATCH", "no launch intent for " + pkg);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        }
        getApplicationContext().startActivity(intent);
    }
}
