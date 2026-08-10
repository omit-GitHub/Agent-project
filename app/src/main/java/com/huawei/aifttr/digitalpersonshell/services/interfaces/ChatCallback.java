package com.huawei.aifttr.digitalpersonshell.services.interfaces;

/**
 * WebSocket 对话回调契约（T-WS-04 / F-WS-04）。
 * <p>
 * 由 {@code WebSocketChatService} 调用，{@code VoiceGateway} 实现：
 * 收到 stream.delta 增量→ {@link #onDelta} 送 TTS 播报；
 * 收到 stream_end→ {@link #onStreamEnd} 结束本轮；
 * 异常/超时耗尽→ {@link #onError} 兜底。
 */
public interface ChatCallback {

    /**
     * 收到一段 stream.delta 增量文本。
     *
     * @param delta 本次增量片段
     * @param msgId  消息 id（日志/区分片段用）
     */
    void onDelta(String delta, String msgId);

    /**
     * 收到 stream_end，本轮对话结束。
     */
    void onStreamEnd();

    /**
     * 对话异常（建链失败/超时耗尽/非法 JSON）。
     *
     * @param msg 错误信息
     */
    void onError(String msg);
}
