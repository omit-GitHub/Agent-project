package com.guiagent.executor;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * RFC 6455 握手服务端逻辑(纯逻辑,无 Android 依赖,JVM 可单测)。
 * 计算 Sec-WebSocket-Accept、解析/校验 Upgrade 请求、构造 101 响应。
 */
public final class WsHandshake {

    /** RFC 6455 §1.3 固定 GUID。 */
    static final String GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

    private WsHandshake() {
    }

    /** 计算 Sec-WebSocket-Accept = base64( sha1( key + GUID ) )。 */
    public static String computeAccept(String key) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-1");
            byte[] digest = md.digest((key + GUID).getBytes(StandardCharsets.UTF_8));
            return base64(digest);
        } catch (Exception e) {
            throw new RuntimeException("sha1 failed", e);
        }
    }

    /** 构造 101 Switching Protocols 响应(含正确 Accept 头)。 */
    public static String buildResponse(String key) {
        return "HTTP/1.1 101 Switching Protocols\r\n"
                + "Upgrade: websocket\r\n"
                + "Connection: Upgrade\r\n"
                + "Sec-WebSocket-Accept: " + computeAccept(key) + "\r\n"
                + "\r\n";
    }

    /** 从 HTTP 请求头文本提取 Sec-WebSocket-Key;缺失返回 null。 */
    public static String extractKey(String request) {
        String v = headerValue(request, "Sec-WebSocket-Key");
        return v == null || v.isEmpty() ? null : v;
    }

    /** 是否为合法 Upgrade 请求(含 Upgrade: websocket 与 Connection: Upgrade,大小写不敏感)。 */
    public static boolean isUpgrade(String request) {
        String upgrade = headerValue(request, "Upgrade");
        String connection = headerValue(request, "Connection");
        return upgrade != null && upgrade.toLowerCase().contains("websocket")
                && connection != null && connection.toLowerCase().contains("upgrade");
    }

    /** 校验:是 Upgrade 请求且含 Sec-WebSocket-Key。 */
    public static boolean validate(String request) {
        return isUpgrade(request) && extractKey(request) != null;
    }

    // ---------- 内部 ----------

    /** 按行扫描取某 header 值(大小写不敏感键),无则 null。 */
    private static String headerValue(String request, String name) {
        String[] lines = request.split("\r\n");
        for (String line : lines) {
            int colon = line.indexOf(':');
            if (colon <= 0) continue;
            String key = line.substring(0, colon).trim();
            if (key.equalsIgnoreCase(name)) {
                return line.substring(colon + 1).trim();
            }
        }
        return null;
    }

    /** 纯 Java Base64 编码(避免 android.util.Base64 在 JVM 单测炸、java.util.Base64 需 API26+)。 */
    private static final char[] B64 =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".toCharArray();

    static String base64(byte[] b) {
        StringBuilder sb = new StringBuilder((b.length + 2) / 3 * 4);
        for (int i = 0; i < b.length; i += 3) {
            int n = ((b[i] & 0xff) << 16)
                    | (i + 1 < b.length ? (b[i + 1] & 0xff) << 8 : 0)
                    | (i + 2 < b.length ? (b[i + 2] & 0xff) : 0);
            sb.append(B64[(n >>> 18) & 0x3f]);
            sb.append(B64[(n >>> 12) & 0x3f]);
            sb.append(i + 1 < b.length ? B64[(n >>> 6) & 0x3f] : '=');
            sb.append(i + 2 < b.length ? B64[n & 0x3f] : '=');
        }
        return sb.toString();
    }
}
