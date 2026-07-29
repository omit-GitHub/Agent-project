package com.guiagent.executor;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** AccessibilityNodeInfo 树遍历/匹配/序列化。 */
public class Nodes {

    /** DFS 前序遍历,按 Match 过滤,返回命中列表(前 limit 个)。 */
    public static List<AccessibilityNodeInfo> find(AccessibilityNodeInfo root, Match m) {
        List<AccessibilityNodeInfo> out = new ArrayList<>();
        if (root == null) return out;
        int lim = m.limit != null ? m.limit : 500;
        dfs(root, m, out, lim);
        return out;
    }

    private static void dfs(AccessibilityNodeInfo n, Match m, List<AccessibilityNodeInfo> out, int lim) {
        if (out.size() >= lim) return;
        if (match(n, m)) out.add(n);
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo c = n.getChild(i);
            if (c == null) continue;
            dfs(c, m, out, lim);
        }
    }

    private static boolean match(AccessibilityNodeInfo n, Match m) {
        if (m.text != null) {
            CharSequence t = n.getText();
            if (t == null || !t.toString().contains(m.text)) return false;
        }
        if (m.id != null) {
            String rid = n.getViewIdResourceName();
            if (rid == null || !idMatches(rid, m.id)) return false;
        }
        if (m.desc != null) {
            CharSequence d = n.getContentDescription();
            if (d == null || !d.toString().contains(m.desc)) return false;
        }
        if (m.cls != null) {
            CharSequence c = n.getClassName();
            if (c == null || !c.toString().contains(m.cls)) return false;
        }
        return true;
    }

    /** 完整 res-id(pkg:id/name)与短名(name)都接受。 */
    private static boolean idMatches(String full, String q) {
        if (full.equals(q)) return true;
        int idx = full.lastIndexOf(":id/");
        String shortName = idx >= 0 ? full.substring(idx + 4) : full;
        return shortName.equals(q);
    }

    /** 点击/长按目标:取自身或最近的可点击祖先。 */
    public static AccessibilityNodeInfo clickableTarget(AccessibilityNodeInfo n) {
        AccessibilityNodeInfo cur = n;
        while (cur != null) {
            if (cur.isClickable()) return cur;
            cur = cur.getParent();
        }
        return n;
    }

    public static JSONObject rectJson(Rect r) throws JSONException {
        return new JSONObject().put("l", r.left).put("t", r.top).put("r", r.right).put("b", r.bottom);
    }

    /** 节点 -> JSON(扁平,不含 children)。inc=null 时输出全部常用字段。 */
    public static JSONObject flatJson(AccessibilityNodeInfo n, Set<String> inc) throws JSONException {
        JSONObject o = new JSONObject();
        boolean all = inc == null;
        if (all || inc.contains("bounds")) {
            Rect b = new Rect();
            n.getBoundsInScreen(b);
            o.put("bounds", rectJson(b));
        }
        if (all || inc.contains("text")) {
            CharSequence t = n.getText();
            o.put("text", t == null ? "" : t.toString());
        }
        if (all || inc.contains("id")) {
            String id = n.getViewIdResourceName();
            o.put("id", id == null ? "" : id);
        }
        if (all || inc.contains("cls")) {
            CharSequence c = n.getClassName();
            o.put("cls", c == null ? "" : c.toString());
        }
        if (all || inc.contains("desc")) {
            CharSequence d = n.getContentDescription();
            o.put("desc", d == null ? "" : d.toString());
        }
        if (all || inc.contains("clickable")) o.put("clickable", n.isClickable());
        if (all || inc.contains("scrollable")) o.put("scrollable", n.isScrollable());
        if (all || inc.contains("enabled")) o.put("enabled", n.isEnabled());
        return o;
    }

    /** 节点 -> JSON(含 children,递归到 maxDepth)。用于 dump。 */
    public static JSONObject treeJson(AccessibilityNodeInfo n, Set<String> inc, int maxDepth, int depth) throws JSONException {
        JSONObject o = flatJson(n, inc);
        if (depth < maxDepth) {
            JSONArray arr = new JSONArray();
            for (int i = 0; i < n.getChildCount(); i++) {
                AccessibilityNodeInfo c = n.getChild(i);
                if (c == null) continue;
                arr.put(treeJson(c, inc, maxDepth, depth + 1));
            }
            o.put("children", arr);
        }
        return o;
    }
}
