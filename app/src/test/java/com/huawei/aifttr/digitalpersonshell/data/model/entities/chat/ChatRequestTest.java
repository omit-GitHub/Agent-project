package com.huawei.aifttr.digitalpersonshell.data.model.entities.chat;

import org.junit.Test;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * ChatRequest 请求模型序列化测试（T-WS-01 / S-WS-03）。
 */
public class ChatRequestTest {

    @Test
    public void toJson_containsTypeAndIdAndMethodAndText() {
        ChatRequest request = new ChatRequest("abc-uuid", "帮我讲个故事");
        JsonObject json = JsonParser.parseString(request.toJson()).getAsJsonObject();

        assertEquals(ChatConfig.REQ_TYPE, json.get("type").getAsString());
        assertEquals("abc-uuid", json.get("id").getAsString());
        assertEquals(ChatConfig.METHOD_CHAT_SEND, json.get("method").getAsString());
        assertEquals("帮我讲个故事", json.getAsJsonObject("params").get("text").getAsString());
    }

    @Test
    public void toJson_differentSessionIdDistinct() {
        String a = new ChatRequest("uuid-a", "你好").toJson();
        String b = new ChatRequest("uuid-b", "你好").toJson();
        assertTrue(a.contains("uuid-a"));
        assertTrue(b.contains("uuid-b"));
        assertTrue(!a.equals(b));
    }
}
