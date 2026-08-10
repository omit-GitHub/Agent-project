package com.huawei.aifttr.digitalpersonshell.services;

import org.junit.Test;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatSocketListener;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketConnection;

import static org.junit.Assert.assertNotNull;

/**
 * OkHttpWebSocketFactory 集成测试（T-WS-07）。
 * <p>
 * 仅验证 {@code open} 同步返回非空连接（newWebSocket 不阻塞）；实际建链/收发为真机/集成验证。
 */
public class OkHttpWebSocketFactoryTest {

    @Test
    public void open_returnsNonNullConnection() {
        OkHttpWebSocketFactory factory = new OkHttpWebSocketFactory();
        ChatSocketListener listener = new ChatSocketListener() {
            @Override
            public void onOpen() {
            }

            @Override
            public void onMessage(String data) {
            }

            @Override
            public void onFailure(Throwable t) {
            }

            @Override
            public void onClosed(int code, String reason) {
            }
        };
        WebSocketConnection connection = factory.open("ws://127.0.0.1:17000/ws?sessionId=test", listener);
        assertNotNull(connection);
        connection.cancel();
    }
}
