package com.huawei.aifttr.digitalpersonshell.data.model.entities.chat;

import com.google.gson.JsonObject;
import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;

/**
 * WebSocket 对话请求模型（T-WS-01 / S-WS-03）。
 * <p>
 * 请求体：{@code { "type":"req", "id":<sessionId>, "method":"chat.send", "params":{"text":<ASR文本>} }}。
 * {@code id} 与 URL 的 {@code sessionId} 保持一致（同一 uuid）。
 */
public class ChatRequest {

    private final String id;
    private final String text;

    /**
     * @param id   会话 id（与 URL sessionId 一致）
     * @param text ASR 最终拾音文本
     */
    public ChatRequest(String id, String text) {
        this.id = id;
        this.text = text;
    }

    public String getId() {
        return id;
    }

    public String getText() {
        return text;
    }

    /**
     * 序列化为 JSON 字符串。
     *
     * @return 请求体 JSON
     */
    public String toJson() {
        JsonObject params = new JsonObject();
        params.addProperty("text", text);
        JsonObject root = new JsonObject();
        root.addProperty("type", ChatConfig.REQ_TYPE);
        root.addProperty("id", id);
        root.addProperty("method", ChatConfig.METHOD_CHAT_SEND);
        root.add("params", params);
        return root.toString();
    }
}
