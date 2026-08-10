package com.huawei.aifttr.digitalpersonshell.services.interfaces;

/**
 * WebSocket 连接端口（T-WS-04，解耦 okhttp3.WebSocket）。
 * <p>
 * 抽象发送与取消能力，便于单测 mock。
 */
public interface WebSocketConnection {

    /**
     * 发送文本消息。
     *
     * @param message 文本
     * @return 是否入队成功
     */
    boolean send(String message);

    /** 取消连接（立即释放）。 */
    void cancel();
}
