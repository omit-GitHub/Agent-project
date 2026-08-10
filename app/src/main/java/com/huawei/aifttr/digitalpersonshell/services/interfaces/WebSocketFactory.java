package com.huawei.aifttr.digitalpersonshell.services.interfaces;

/**
 * WebSocket 工厂端口（T-WS-04）。
 * <p>
 * 生产实现 {@code OkHttpWebSocketFactory} 用 okhttp 建链；单测用 mock 返回 mock 连接并捕获监听器。
 */
public interface WebSocketFactory {

    /**
     * 建立 WebSocket 连接。
     *
     * @param url      完整 URL
     * @param listener 事件监听器
     * @return 连接端口
     */
    WebSocketConnection open(String url, ChatSocketListener listener);
}
