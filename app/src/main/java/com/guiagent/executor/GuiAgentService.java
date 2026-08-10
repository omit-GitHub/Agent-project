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

import org.json.JSONObject;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

// 命令已迁移至 Python (server.py + registry.py)，通过 HTTP :8765 调用 Python 进程。
// Java 侧仅保留 WS 原子操作服务(:8322)。

/**
 * 无障碍服务:系统在「设置→无障碍」开启后常驻;onServiceConnected 起 WebSocket
 * 服务(:8322) + HTTP 复合命令服务(:8765),接收指令并翻译为无障碍动作。不依赖 root/adb。
 */
public class GuiAgentService extends AccessibilityService {

    private static final String TAG = "guiagent";
    private static volatile GuiAgentService instance;

    private WsCommandServer server;
    private DpadAdapter dpad;
    // HTTP 复合命令服务已迁移至 Python (server.py :8765)

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
        if (dpad != null) dpad.close();
        dpad = new DpadAdapter(getApplicationContext());
        Log.i(TAG, "service connected, ws server up");
        // HTTP 复合命令服务已迁移至 Python (server.py :8765)，需单独启动:
        //   python server.py --port 8765
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
        if (dpad != null) {
            dpad.close();
            dpad = null;
        }
        if (instance == this) instance = null;
        return super.onUnbind(intent);
    }

    // ---------- 感知 ----------
    public AccessibilityNodeInfo root() {
        return getRootInActiveWindow();
    }

    /**
     * 搜索所有窗口的 UI 树，找 text 或 desc 包含 pattern 的节点。
     * 清晰度面板等弹窗可能在非活跃窗口中，getRootInActiveWindow() 搜不到。
     */
    /**
     * 搜索所有窗口的 UI 树，找 text 或 desc 包含 pattern 的节点。
     * 清晰度面板等弹窗可能在非活跃窗口中，getRootInActiveWindow() 搜不到。
     */
    public AccessibilityNodeInfo findTextInAllWindows(String pattern) {
        List<android.view.accessibility.AccessibilityWindowInfo> windows = getWindows();
        if (windows != null) {
            for (android.view.accessibility.AccessibilityWindowInfo w : windows) {
                AccessibilityNodeInfo root = w.getRoot();
                if (root == null) continue;
                AccessibilityNodeInfo hit = findByTextDFS(root, pattern);
                if (hit != null) return hit;
            }
        }
        // 兜底: 活跃窗口
        AccessibilityNodeInfo activeRoot = getRootInActiveWindow();
        if (activeRoot != null) {
            return findByTextDFS(activeRoot, pattern);
        }
        return null;
    }

    private AccessibilityNodeInfo findByTextDFS(AccessibilityNodeInfo node, String pattern) {
        if (node == null) return null;
        CharSequence text = node.getText();
        if (text != null && text.toString().contains(pattern)) return node;
        CharSequence desc = node.getContentDescription();
        if (desc != null && desc.toString().contains(pattern)) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            AccessibilityNodeInfo hit = findByTextDFS(child, pattern);
            if (hit != null) return hit;
        }
        return null;
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
        Log.i(TAG, "gesture() called: points=" + points.size() + " duration=" + durationMs
                + " first=(" + points.get(0)[0] + "," + points.get(0)[1] + ")");
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
        try {
            dispatchGesture(gd, new GestureResultCallback() {
                @Override
                public void onCompleted(GestureDescription gestureDescription) {
                    Log.i(TAG, "gesture onCompleted");
                    ok[0] = true;
                    latch.countDown();
                }

                @Override
                public void onCancelled(GestureDescription gestureDescription) {
                    Log.w(TAG, "gesture onCancelled");
                    ok[0] = false;
                    latch.countDown();
                }
            }, null);
            Log.i(TAG, "dispatchGesture() called OK");
        } catch (Exception e) {
            Log.e(TAG, "dispatchGesture() threw exception", e);
            return false;
        }
        try {
            boolean completed = latch.await(durationMs + 2000, TimeUnit.MILLISECONDS);
            Log.i(TAG, "gesture result: ok=" + ok[0] + " completed=" + completed);
        } catch (InterruptedException ignored) {
        }
        return ok[0];
    }

    // ---------- 系统级 ----------
    public boolean global(int actionId) {
        return performGlobalAction(actionId);
    }

    /** Sends one allow-listed remote-control key through the vendor service. */
    public JSONObject remoteKey(String key, long timeoutMs) {
        DpadAdapter adapter = dpad;
        if (adapter == null) throw new Err("DPAD_UNAVAILABLE", "remote-control service is not initialized");
        return adapter.send(key, timeoutMs);
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

    // 命令注册已迁移至 Python (server.py register_all_commands())
}
