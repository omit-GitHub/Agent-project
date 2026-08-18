package com.guiagent.executor;

import android.accessibilityservice.AccessibilityService;
import android.os.Build;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * instruction-protocol v1.x 指令分发:一行 NDJSON 请求 -> 一行 NDJSON 响应。
 * 请求 {id,op,args};响应 {id,ok,data} 或 {id,ok:false,err:{code,msg}}。
 */
public class Protocol {

    public static String handle(GuiAgentService svc, String line) {
        String id;
        String op;
        JSONObject args;
        try {
            JSONObject req = new JSONObject(line);
            id = req.has("id") ? req.get("id").toString() : "";
            op = req.optString("op", "");
            args = (req.has("args") && req.get("args") instanceof JSONObject)
                    ? req.getJSONObject("args") : new JSONObject();
        } catch (Exception e) {
            return errResp("", "BAD_ARGS", "parse error: " + (e.getMessage() == null ? "" : e.getMessage()));
        }
        try {
            JSONObject data = dispatch(svc, op, args);
            return okResp(id, data);
        } catch (Err e) {
            return errResp(id, e.code, e.getMessage() == null ? "" : e.getMessage());
        } catch (Exception e) {
            return errResp(id, "INTERNAL", e.getMessage() == null ? e.toString() : e.getMessage());
        }
    }

    private static JSONObject dispatch(GuiAgentService svc, String op, JSONObject a) throws Exception {
        switch (op) {
            case "ping": return ping(svc);
            case "dump": return dump(svc, a);
            case "find": return find(svc, a);
            case "click_node": return clickNode(svc, a, false);
            case "long_click_node": return clickNode(svc, a, true);
            case "set_text": return setText(svc, a, false);
            case "set_text_fallback": return setText(svc, a, true);
            case "scroll_node": return scrollNode(svc, a);
            case "tap": return tap(svc, a);
            case "long_press": return longPress(svc, a);
            case "swipe": return swipe(svc, a);
            case "gesture": return gesture(svc, a);
            case "global": return global(svc, a);
            case "remote_key": return remoteKey(svc, a);
            case "wait": return wait(svc, a);
            case "start": return start(svc, a);
            case "": throw new Err("BAD_ARGS", "missing op");
            default: throw new Err("UNKNOWN_OP", "unknown op: " + op);
        }
    }

    // ---------- 响应构造 ----------
    private static String okResp(String id, JSONObject data) throws JSONException {
        return new JSONObject().put("id", id).put("ok", true).put("data", data).toString();
    }

    private static String errResp(String id, String code, String msg) {
        try {
            return new JSONObject().put("id", id).put("ok", false)
                    .put("err", new JSONObject().put("code", code).put("msg", msg)).toString();
        } catch (JSONException e) {
            return "{\"id\":\"" + id + "\",\"ok\":false,\"err\":{\"code\":\"" + code + "\"}}";
        }
    }

    // ---------- 读 ----------
    private static JSONObject ping(GuiAgentService svc) throws JSONException {
        android.util.DisplayMetrics dm = svc.getResources().getDisplayMetrics();
        // 取前台窗口的真实包名（svc.getPackageName() 返回的是无障碍服务自己的包名，错误）
        String pkg = "";
        AccessibilityNodeInfo root = svc.root();
        if (root != null) {
            CharSequence pkgCs = root.getPackageName();
            if (pkgCs != null) pkg = pkgCs.toString();
        }
        return new JSONObject()
                .put("pong", true)
                .put("pkg", pkg)
                .put("screen", new JSONObject()
                        .put("w", dm.widthPixels)
                        .put("h", dm.heightPixels)
                        .put("sdk", Build.VERSION.SDK_INT));
    }

    private static JSONObject dump(GuiAgentService svc, JSONObject a) throws JSONException {
        Set<String> inc = parseInclude(a);
        int depth = a.optInt("depth", 50);
        AccessibilityNodeInfo root = svc.root();
        JSONObject w = root != null ? Nodes.treeJson(root, inc, depth, 0) : new JSONObject();
        // 同样取前台窗口的真实包名
        String pkg = "";
        if (root != null) {
            CharSequence pkgCs = root.getPackageName();
            if (pkgCs != null) pkg = pkgCs.toString();
        }
        return new JSONObject().put("pkg", pkg).put("window", w);
    }

    private static JSONObject find(GuiAgentService svc, JSONObject a) throws JSONException {
        Match m = parseMatch(a);
        Set<String> inc = parseInclude(a);
        List<AccessibilityNodeInfo> nodes = svc.findNodes(m);
        JSONArray arr = new JSONArray();
        for (AccessibilityNodeInfo n : nodes) arr.put(Nodes.flatJson(n, inc));
        return new JSONObject().put("nodes", arr);
    }

    // ---------- 节点级 ----------
    private static JSONObject clickNode(GuiAgentService svc, JSONObject a, boolean longClick) throws JSONException {
        Match m = parseMatch(a);
        int idx = a.optInt("index", 0);
        List<AccessibilityNodeInfo> nodes = svc.findNodes(m);
        if (nodes.isEmpty()) throw new Err("NO_MATCH", "no node matches " + m);
        if (idx >= nodes.size()) throw new Err("INDEX_OOB", "index " + idx + " >= " + nodes.size());
        boolean ok = longClick ? svc.longClick(nodes.get(idx)) : svc.click(nodes.get(idx));
        if (!ok) throw new Err("NOT_CLICKABLE", "performAction returned false");
        return new JSONObject().put("clicked", true);
    }

    private static JSONObject setText(GuiAgentService svc, JSONObject a, boolean fallback) throws JSONException {
        // 注意:text 是"要填的值",不能作为匹配条件,故 Match.text=null
        String text = a.optString("text", "");
        Match m = new Match(
                null,
                a.has("id") ? a.getString("id") : null,
                a.has("desc") ? a.getString("desc") : null,
                a.has("cls") ? a.getString("cls") : null,
                a.has("limit") ? a.getInt("limit") : null
        );
        List<AccessibilityNodeInfo> nodes = svc.findNodes(m);
        if (nodes.isEmpty()) throw new Err("NO_MATCH", "no node matches " + m);
        AccessibilityNodeInfo node = nodes.get(0);
        if (!fallback) {
            boolean ok = svc.setText(node, text);
            if (!ok) throw new Err("SET_TEXT_FAILED", "ACTION_SET_TEXT returned false; try set_text_fallback");
            return new JSONObject().put("used", "set_text");
        }
        boolean ok = svc.paste(node, text);
        if (!ok) throw new Err("PASTE_UNSUPPORTED", "ACTION_PASTE returned false");
        return new JSONObject().put("used", "paste");
    }

    private static JSONObject scrollNode(GuiAgentService svc, JSONObject a) throws JSONException {
        Match m = parseMatch(a);
        String dir = a.optString("dir", "");
        int action;
        switch (dir) {
            case "down": case "right": action = AccessibilityNodeInfo.ACTION_SCROLL_FORWARD; break;
            case "up": case "left": action = AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD; break;
            default: throw new Err("BAD_ARGS", "bad dir: " + dir);
        }
        List<AccessibilityNodeInfo> nodes = svc.findNodes(m);
        if (nodes.isEmpty()) throw new Err("NO_MATCH", "no scrollable matches " + m);
        AccessibilityNodeInfo target = nodes.get(0);
        for (AccessibilityNodeInfo n : nodes) {
            if (n.isScrollable()) {
                target = n;
                break;
            }
        }
        boolean ok = svc.scroll(target, action);
        if (!ok) throw new Err("NOT_CLICKABLE", "scroll returned false");
        return new JSONObject().put("scrolled", true);
    }

    // ---------- 坐标级 ----------
    private static JSONObject tap(GuiAgentService svc, JSONObject a) throws JSONException {
        List<float[]> pts = new ArrayList<>();
        pts.add(new float[]{(float) a.optDouble("x", 0), (float) a.optDouble("y", 0)});
        return new JSONObject().put("ok", svc.gesture(pts, 40));
    }

    private static JSONObject longPress(GuiAgentService svc, JSONObject a) throws JSONException {
        long dur = a.optLong("duration", 1000);
        List<float[]> pts = new ArrayList<>();
        pts.add(new float[]{(float) a.optDouble("x", 0), (float) a.optDouble("y", 0)});
        return new JSONObject().put("ok", svc.gesture(pts, dur));
    }

    private static JSONObject swipe(GuiAgentService svc, JSONObject a) throws JSONException {
        long dur = a.optLong("duration", 300);
        List<float[]> pts = new ArrayList<>();
        pts.add(new float[]{(float) a.optDouble("x1", 0), (float) a.optDouble("y1", 0)});
        pts.add(new float[]{(float) a.optDouble("x2", 0), (float) a.optDouble("y2", 0)});
        return new JSONObject().put("ok", svc.gesture(pts, dur));
    }

    private static JSONObject gesture(GuiAgentService svc, JSONObject a) throws JSONException {
        if (!a.has("points")) throw new Err("BAD_ARGS", "missing points");
        JSONArray arr = a.getJSONArray("points");
        long dur = a.optLong("duration", 300);
        List<float[]> pts = new ArrayList<>();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject p = arr.getJSONObject(i);
            pts.add(new float[]{(float) p.optDouble("x", 0), (float) p.optDouble("y", 0)});
        }
        return new JSONObject().put("ok", svc.gesture(pts, dur));
    }

    // ---------- 系统 ----------
    private static JSONObject global(GuiAgentService svc, JSONObject a) throws JSONException {
        String act = a.optString("action", "");
        int ga;
        switch (act) {
            case "back": ga = AccessibilityService.GLOBAL_ACTION_BACK; break;
            case "home": ga = AccessibilityService.GLOBAL_ACTION_HOME; break;
            case "recents": ga = AccessibilityService.GLOBAL_ACTION_RECENTS; break;
            case "notif": ga = AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS; break;
            case "qs": ga = AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS; break;
            case "screenshot":
                if (Build.VERSION.SDK_INT >= 30) {
                    ga = AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT;
                } else {
                    throw new Err("BAD_ARGS", "screenshot needs API30+");
                }
                break;
            default: throw new Err("BAD_ARGS", "bad action: " + act);
        }
        return new JSONObject().put("ok", svc.global(ga));
    }

    // ---------- 遥控器 ----------
    private static JSONObject remoteKey(GuiAgentService svc, JSONObject a) throws JSONException {
        String key = a.optString("key", "").trim();
        if (key.isEmpty()) throw new Err("BAD_ARGS", "missing remote key");
        int repeat = a.optInt("repeat", 1);
        if (repeat < 1 || repeat > 20) throw new Err("BAD_ARGS", "repeat must be between 1 and 20");

        JSONObject last = null;
        for (int i = 0; i < repeat; i++) {
            last = svc.remoteKey(key, 1800L);
            if (i + 1 < repeat) {
                try {
                    Thread.sleep(120L);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new Err("INTERRUPTED", "remote key repeat interrupted");
                }
            }
        }
        return new JSONObject().put("key", last.optString("key", key)).put("repeat", repeat).put("last", last);
    }

    private static JSONObject wait(GuiAgentService svc, JSONObject a) throws JSONException {
        if (a.has("ms")) {
            try {
                Thread.sleep(a.getLong("ms"));
            } catch (InterruptedException ignored) {
            }
            return new JSONObject().put("ok", true);
        }
        if (a.has("event")) throw new Err("BAD_ARGS", "wait event is v1.2; use {ms}");
        throw new Err("BAD_ARGS", "wait needs {ms:int}");
    }

    private static JSONObject start(GuiAgentService svc, JSONObject a) throws JSONException {
        String pkg = a.optString("pkg", "");
        String cls = a.optString("cls", "");
        if (pkg.isEmpty()) throw new Err("BAD_ARGS", "missing pkg");
        svc.launch(pkg, cls.isEmpty() ? null : cls);
        return new JSONObject().put("started", pkg);
    }

    // ---------- 参数解析 ----------
    private static Match parseMatch(JSONObject a) throws JSONException {
        return new Match(
                a.has("text") ? a.getString("text") : null,
                a.has("id") ? a.getString("id") : null,
                a.has("desc") ? a.getString("desc") : null,
                a.has("cls") ? a.getString("cls") : null,
                a.has("limit") ? a.getInt("limit") : null
        );
    }

    private static Set<String> parseInclude(JSONObject a) throws JSONException {
        if (!a.has("include")) return null;
        JSONArray arr = a.getJSONArray("include");
        Set<String> s = new HashSet<>();
        for (int i = 0; i < arr.length(); i++) s.add(arr.getString(i));
        return s;
    }
}
