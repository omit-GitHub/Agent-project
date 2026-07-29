package com.guiagent.executor;

import org.junit.Test;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/**
 * WsHandshake 单元测试(T-001)。纯逻辑,无 Android 依赖,JVM 跑。
 * 覆盖 RFC 6455 握手:Accept 计算、请求头解析、响应构造、校验。
 */
public class WsHandshakeTest {

    // RFC 6455 §1.3 官方向量
    private static final String OFFICIAL_KEY = "dGhlIHNhbXBsZSBub25jZQ==";
    private static final String OFFICIAL_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=";

    private static final String VALID_REQUEST =
            "GET /guiagent HTTP/1.1\r\n" +
            "Host: 192.168.1.10:8322\r\n" +
            "Upgrade: websocket\r\n" +
            "Connection: Upgrade\r\n" +
            "Sec-WebSocket-Key: " + OFFICIAL_KEY + "\r\n" +
            "Sec-WebSocket-Version: 13\r\n" +
            "\r\n";

    // TC-001: Accept 计算 == RFC 官方向量
    @Test
    public void testComputeAcceptKey_rfc6455OfficialVector() {
        assertEquals(OFFICIAL_ACCEPT, WsHandshake.computeAccept(OFFICIAL_KEY));
    }

    // TC-002: 从请求头提取 Sec-WebSocket-Key,并识别 Upgrade
    @Test
    public void testParseHeaders_extractsWebSocketKey() {
        assertEquals(OFFICIAL_KEY, WsHandshake.extractKey(VALID_REQUEST));
        assertTrue(WsHandshake.isUpgrade(VALID_REQUEST));
    }

    // TC-003: 构造 101 响应,含正确 Accept
    @Test
    public void testBuildResponse_returns101AndAccept() {
        String resp = WsHandshake.buildResponse(OFFICIAL_KEY);
        assertTrue("response must start with 101", resp.startsWith("HTTP/1.1 101 Switching Protocols"));
        assertTrue("must contain Upgrade header", resp.contains("Upgrade: websocket"));
        assertTrue("must contain Connection header", resp.contains("Connection: Upgrade"));
        assertTrue("must contain Accept", resp.contains("Sec-WebSocket-Accept: " + OFFICIAL_ACCEPT));
    }

    // TC-004: 缺 Upgrade -> 校验失败
    @Test
    public void testValidateRequest_rejectsMissingUpgrade() {
        String noUpgrade =
                "GET /guiagent HTTP/1.1\r\n" +
                "Host: 192.168.1.10:8322\r\n" +
                "Sec-WebSocket-Key: " + OFFICIAL_KEY + "\r\n" +
                "\r\n";
        assertFalse(WsHandshake.isUpgrade(noUpgrade));
        assertFalse(WsHandshake.validate(noUpgrade));
    }

    // TC-005: 缺 Sec-WebSocket-Key -> 校验失败
    @Test
    public void testValidateRequest_rejectsMissingKey() {
        String noKey =
                "GET /guiagent HTTP/1.1\r\n" +
                "Host: 192.168.1.10:8322\r\n" +
                "Upgrade: websocket\r\n" +
                "Connection: Upgrade\r\n" +
                "\r\n";
        assertEquals(null, WsHandshake.extractKey(noKey));
        assertFalse(WsHandshake.validate(noKey));
    }
}
