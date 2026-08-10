package com.huawei.aifttr.digitalpersonshell.services.interfaces;

/**
 * WebSocket 监听器端口（T-WS-04，解耦 okhttp3.WebSocketListener）。
 * <p>
 * 仅含 String/Throwable/int 原语类型，不泄漏 okhttp 类型，便于纯 JVM 单测。
 */
public interface ChatSocketListener {

    /** 连接已打开，可发送消息。 */
    void onOpen();

    /** 收到文本消息。 */
    void onMessage(String data);

    /** 连接异常。 */
    void onFailure(Throwable t);

    /** 连接已关闭。 */
    void onClosed(int code, String reason);
}
