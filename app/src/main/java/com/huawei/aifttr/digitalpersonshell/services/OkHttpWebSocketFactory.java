package com.huawei.aifttr.digitalpersonshell.services;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatSocketListener;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketConnection;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketFactory;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

/**
 * OkHttp WebSocket 工厂生产实现（T-WS-07）。
 * <p>
 * 把 {@link WebSocketFactory} 端口桥接到 okhttp3：构造 {@link Request}、注册
 * {@link WebSocketListener}，适配为 {@link ChatSocketListener}，返回包装 {@link WebSocket} 的连接。
 *
 * @see WebSocketChatService
 */
public class OkHttpWebSocketFactory implements WebSocketFactory {

    private static final String TAG = "OkHttpWebSocketFactory";

    private final OkHttpClient client;

    public OkHttpWebSocketFactory() {
        this(new OkHttpClient());
    }

    public OkHttpWebSocketFactory(OkHttpClient client) {
        this.client = client;
    }

    @Override
    public WebSocketConnection open(String url, ChatSocketListener listener) {
        Request request = new Request.Builder().url(url).build();
        Logger.info(TAG, "[CHAT] open ws: " + url);
        WebSocket ws = client.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                listener.onOpen();
            }

            @Override
            public void onMessage(WebSocket webSocket, String text) {
                listener.onMessage(text);
            }

            @Override
            public void onClosing(WebSocket webSocket, int code, String reason) {
                listener.onClosed(code, reason);
            }

            @Override
            public void onClosed(WebSocket webSocket, int code, String reason) {
                listener.onClosed(code, reason);
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                listener.onFailure(t);
            }
        });
        return new OkHttpConnection(ws);
    }

    /** okhttp WebSocket 包装。 */
    private static class OkHttpConnection implements WebSocketConnection {
        private final WebSocket webSocket;

        OkHttpConnection(WebSocket webSocket) {
            this.webSocket = webSocket;
        }

        @Override
        public boolean send(String message) {
            return webSocket.send(message);
        }

        @Override
        public void cancel() {
            webSocket.cancel();
        }
    }
}
