package com.huawei.aifttr.digitalpersonshell.constants;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

/**
 * ChatConfig 对话常量测试（T-WS-01）。
 */
public class ChatConfigTest {

    @Test
    public void wsConstants_areComplete() {
        assertEquals("ws://", ChatConfig.WS_SCHEME);
        assertEquals("17000", ChatConfig.WS_PORT);
        assertEquals("chat.send", ChatConfig.METHOD_CHAT_SEND);
        assertEquals("req", ChatConfig.REQ_TYPE);
        assertEquals("stream.delta", ChatConfig.EVENT_STREAM_DELTA);
        assertEquals("stream.done", ChatConfig.EVENT_STREAM_END);
        assertEquals(30L, ChatConfig.TIMEOUT_SECONDS);
        assertNotNull(ChatConfig.ERROR_FALLBACK_TEXT);
        assertTrue(ChatConfig.ERROR_FALLBACK_TEXT.length() > 0);
    }
}
