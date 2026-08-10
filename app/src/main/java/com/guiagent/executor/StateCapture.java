package com.guiagent.executor;

import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * 前台状态采集：活跃窗口包名 + 页面前若干条可见文本。
 * get_state 命令与 play 后状态确认共用。
 */
public final class StateCapture {

    private static final int MAX_SUMMARY_TEXTS = 12;
    private static final int MAX_TEXT_LEN = 30;

    private StateCapture() {
    }

    /**
     * 采集当前前台状态。
     *
     * @return {"pkg": "...", "summary": [...]}；无活跃窗口时 pkg 为空串、summary 为空
     */
    public static JsonObject capture(GuiAgentService service) {
        JsonObject data = new JsonObject();
        JsonArray summary = new JsonArray();
        AccessibilityNodeInfo root = service.root();
        if (root != null) {
            CharSequence pkg = root.getPackageName();
            data.addProperty("pkg", pkg == null ? "" : pkg.toString());
            Set<String> texts = new LinkedHashSet<>();
            collectTexts(root, texts);
            for (String t : texts) {
                summary.add(t);
            }
        } else {
            data.addProperty("pkg", "");
        }
        data.add("summary", summary);
        return data;
    }

    /** DFS 收集去重后的可见文本，够 MAX_SUMMARY_TEXTS 条即停。 */
    private static void collectTexts(AccessibilityNodeInfo node, Set<String> out) {
        if (node == null || out.size() >= MAX_SUMMARY_TEXTS) {
            return;
        }
        CharSequence text = node.getText();
        if (text != null) {
            String t = text.toString().trim();
            if (!t.isEmpty() && t.length() <= MAX_TEXT_LEN) {
                out.add(t);
            }
        }
        for (int i = 0; i < node.getChildCount() && out.size() < MAX_SUMMARY_TEXTS; i++) {
            collectTexts(node.getChild(i), out);
        }
    }

    private static final long POLL_INTERVAL_MS = 300;

    /**
     * 命令执行后等待页面稳定并采集：每 300ms 采一次，最多 capMs。返回条件：
     * <ul>
     *   <li>前台包名离开基线（App 切换）且连续两次采集相同 —— 覆盖 play/start 的跳转链；</li>
     *   <li>包名未变但树发生过变化且已稳定 —— 覆盖面板开合等内容变化；</li>
     *   <li>否则等到 capMs —— "一直没动静"本身就是动作未生效的信号，不提前退出
     *      （提前退出会在 App 冷启动的头几百毫秒误判"已稳定"而返回旧状态）。</li>
     * </ul>
     */
    public static JsonObject awaitStable(GuiAgentService service, String baselinePkg, long capMs) {
        JsonObject prev = capture(service);
        boolean treeChanged = false;
        long deadline = System.currentTimeMillis() + capMs;
        while (System.currentTimeMillis() < deadline) {
            try {
                Thread.sleep(POLL_INTERVAL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            JsonObject cur = capture(service);
            String pkg = cur.get("pkg").getAsString();
            boolean pkgLeftBaseline = !pkg.isEmpty() && !pkg.equals(baselinePkg);
            if (same(cur, prev)) {
                if (pkgLeftBaseline || treeChanged) {
                    return cur;
                }
            } else {
                treeChanged = true;
            }
            prev = cur;
        }
        return prev;
    }

    private static boolean same(JsonObject a, JsonObject b) {
        return a.get("pkg").getAsString().equals(b.get("pkg").getAsString())
                && a.getAsJsonArray("summary").equals(b.getAsJsonArray("summary"));
    }
}
