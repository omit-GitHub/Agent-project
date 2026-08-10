package com.huawei.aifttr.digitalpersonshell.services;

import org.junit.Before;
import org.junit.Test;
import org.mockito.ArgumentCaptor;

import java.util.Optional;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatCallback;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatSocketListener;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketConnection;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketFactory;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IpSupplier;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeast;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * WebSocketChatService 核心测试（T-WS-05 / S-WS-04/08~16）。
 * <p>
 * 注入 mock {@link WebSocketFactory} 返回 mock {@link WebSocketConnection}，
 * 用 {@link ArgumentCaptor} 捕获 {@link ChatSocketListener} 后手动触发 onOpen/onMessage/onFailure，
 * 验证建链/发送/解析/超时/重连/打断；无真实网络与线程。
 */
public class WebSocketChatServiceTest {

    private IpSupplier ipSupplier;
    private WebSocketFactory factory;
    private WebSocketConnection connection;
    private ScheduledExecutorService scheduler;
    private ChatCallback callback;
    private WebSocketChatService service;
    private ChatSocketListener listener;
    private long nextTurnId;

    @Before
    public void setUp() {
        ipSupplier = () -> Optional.of("192.168.1.25");
        factory = mock(WebSocketFactory.class);
        connection = mock(WebSocketConnection.class);
        scheduler = mock(ScheduledExecutorService.class);
        callback = mock(ChatCallback.class);

        when(factory.open(any(), any())).thenAnswer(inv -> {
            listener = inv.getArgument(1);
            return connection;
        });

        service = new WebSocketChatService(ipSupplier, factory, scheduler, callback);
    }

    /** S-WS-04 URL 拼装。 */
    @Test
    public void buildUrl_appendsSchemePortPathAndSessionId() {
        assertEquals("ws://192.168.1.1:17000/ws?sessionId=abc-uuid",
                WebSocketChatService.buildUrl("192.168.1.1", "abc-uuid"));
    }

    /** S-WS-08 建链 + 发送：startChat→factory.open(url)；onOpen→connection.send(请求体)。 */
    @Test
    public void startChat_opensFactoryAndSendsChatRequest() {
        startTurn("帮我讲个故事");

        ArgumentCaptor<String> urlCaptor = ArgumentCaptor.forClass(String.class);
        verify(factory, times(1)).open(urlCaptor.capture(), any());
        String url = urlCaptor.getValue();
        assertTrue(url.startsWith("ws://192.168.1.1:17000/ws?sessionId="));
        // 超时已调度
        verify(scheduler, atLeast(1)).schedule(any(Runnable.class), eq(ChatConfig.TIMEOUT_SECONDS),
                eq(TimeUnit.SECONDS));

        listener.onOpen();

        ArgumentCaptor<String> msgCaptor = ArgumentCaptor.forClass(String.class);
        verify(connection, times(1)).send(msgCaptor.capture());
        JsonObject json = JsonParser.parseString(msgCaptor.getValue()).getAsJsonObject();
        assertEquals("chat.send", json.get("method").getAsString());
        assertEquals("帮我讲个故事", json.getAsJsonObject("params").get("text").getAsString());
    }

    /** S-WS-08b id 与 URL sessionId 一致。 */
    @Test
    public void startChat_requestIdEqualsSessionId() {
        startTurn("你好");
        ArgumentCaptor<String> urlCaptor = ArgumentCaptor.forClass(String.class);
        verify(factory).open(urlCaptor.capture(), any());
        String sessionId = urlCaptor.getValue()
                .substring(urlCaptor.getValue().indexOf("sessionId=") + "sessionId=".length());

        listener.onOpen();
        ArgumentCaptor<String> msgCaptor = ArgumentCaptor.forClass(String.class);
        verify(connection).send(msgCaptor.capture());
        JsonObject json = JsonParser.parseString(msgCaptor.getValue()).getAsJsonObject();
        assertEquals(sessionId, json.get("id").getAsString());
    }

    /** 连续语音轮次复用 URL sessionId，Agent 端据此复用同一 ChatWorker/历史。 */
    @Test
    public void startTurn_multipleTurns_reusesAgentSessionId() {
        startTurn("第一轮");
        startTurn("第二轮");

        ArgumentCaptor<String> urls = ArgumentCaptor.forClass(String.class);
        verify(factory, times(2)).open(urls.capture(), any());
        String firstSessionId = urls.getAllValues().get(0)
                .substring(urls.getAllValues().get(0).indexOf("sessionId=") + "sessionId=".length());
        String secondSessionId = urls.getAllValues().get(1)
                .substring(urls.getAllValues().get(1).indexOf("sessionId=") + "sessionId=".length());

        assertEquals(firstSessionId, secondSessionId);
    }

    /** 每次显式唤醒开始新 Agent session，不能继承上一唤醒会话。 */
    @Test
    public void startTurn_differentConversations_useDifferentSessionIds() {
        service.startTurn("conversation-1", ++nextTurnId, "第一轮");
        service.startTurn("conversation-2", ++nextTurnId, "第二轮");

        ArgumentCaptor<String> urls = ArgumentCaptor.forClass(String.class);
        verify(factory, times(2)).open(urls.capture(), any());
        String firstSessionId = urls.getAllValues().get(0)
                .substring(urls.getAllValues().get(0).indexOf("sessionId=") + "sessionId=".length());
        String secondSessionId = urls.getAllValues().get(1)
                .substring(urls.getAllValues().get(1).indexOf("sessionId=") + "sessionId=".length());

        org.junit.Assert.assertNotEquals(firstSessionId, secondSessionId);
    }

    /** S-WS-09 stream.delta→onDelta。 */
    @Test
    public void onMessage_streamDelta_callsOnDelta() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage(deltaMessage("好的！", "msg-1", 1));

        verify(callback, times(1)).onDelta("好的！", "msg-1");
    }

    /** S-WS-10 多 delta 顺序回调。 */
    @Test
    public void onMessage_multipleDeltas_callsOnDeltaInOrder() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage(deltaMessage("好的！", "msg-1", 1));
        listener.onMessage(deltaMessage("我给你讲", "msg-1", 2));

        org.mockito.InOrder inOrder = org.mockito.Mockito.inOrder(callback);
        inOrder.verify(callback).onDelta("好的！", "msg-1");
        inOrder.verify(callback).onDelta("我给你讲", "msg-1");
    }

    /** 每个流式帧都重置超时，避免首帧后流卡死永久挂起。 */
    @Test
    public void onMessage_resetsTimeoutForCurrentRound() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage(deltaMessage("好的！", "msg-1", 1));

        verify(scheduler, times(3)).schedule(any(Runnable.class), eq(ChatConfig.TIMEOUT_SECONDS),
                eq(TimeUnit.SECONDS));
    }

    /** S-WS-11 stream_end→onStreamEnd + 关闭连接。 */
    @Test
    public void onMessage_streamEnd_callsOnStreamEndAndCancels() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage(streamEndMessage());

        verify(callback, times(1)).onStreamEnd();
        verify(connection, atLeast(1)).cancel();
    }

    /** S-WS-12 传输超时→立即 onError 兜底，不重连（错误即退出，不卡用户）。 */
    @Test
    public void timeoutFires_callsOnErrorWithoutReconnect() {
        startTurn("讲个故事");
        // 不触发 onOpen，仅捕获 startTurn 阶段调度的超时 Runnable 并执行
        ArgumentCaptor<Runnable> runnable = ArgumentCaptor.forClass(Runnable.class);
        verify(scheduler, times(1)).schedule(runnable.capture(), eq(ChatConfig.TIMEOUT_SECONDS),
                eq(TimeUnit.SECONDS));
        runnable.getValue().run();

        verify(connection, atLeast(1)).cancel();
        verify(callback, times(1)).onError(any());
        // 不重连：仅初始 1 次 open
        verify(factory, times(1)).open(any(), any());
    }

    /** S-WS-13 失败→立即 onError 兜底，不重连。 */
    @Test
    public void onFailure_immediatelyCallsOnErrorWithoutReconnect() {
        startTurn("讲个故事");
        listener.onFailure(new RuntimeException("fail-1"));

        verify(callback, times(1)).onError(any());
        // 不重连：仅初始 1 次 open
        verify(factory, times(1)).open(any(), any());
    }

    /** 未收到 stream_end 就关闭连接→回调上层错误复位。 */
    @Test
    public void onClosed_beforeStreamEnd_callsOnError() {
        startTurn("讲个故事");
        listener.onClosed(1006, "abnormal");

        verify(callback, times(1)).onError(any());
    }

    /** 旧轮迟到 stream_end 不得结束或取消新轮。 */
    @Test
    public void staleStreamEnd_afterNewChat_isIgnored() {
        startTurn("第一轮");
        ChatSocketListener firstListener = listener;
        startTurn("第二轮");
        ChatSocketListener secondListener = listener;

        firstListener.onMessage(streamEndMessage());
        verify(callback, never()).onStreamEnd();

        secondListener.onMessage(streamEndMessage());
        verify(callback, times(1)).onStreamEnd();
    }

    /** S-WS-14 stream_end 后断开不上报。 */
    @Test
    public void onFailure_afterStreamEnd_doesNotReportError() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage(streamEndMessage());
        listener.onFailure(new RuntimeException("closed"));

        verify(callback, never()).onError(any());
        verify(factory, times(1)).open(any(), any()); // 未重连
    }

    /** S-WS-15 非法 JSON→onError，不抛异常。 */
    @Test
    public void onMessage_invalidJson_callsOnErrorNoThrow() {
        startTurn("讲个故事");
        listener.onOpen();
        listener.onMessage("not-a-json");

        verify(callback, times(1)).onError(any());
    }

    /** S-WS-16 cancelChat→cancel 连接 + 取消超时；后续 onFailure 不上报。 */
    @Test
    public void cancelChat_cancelsConnectionAndTimeout() {
        startTurn("讲个故事");
        service.cancelChat();

        verify(connection, atLeast(1)).cancel();
        // 取消后再 onFailure 不应触发 onError（isChatting=false）
        listener.onFailure(new RuntimeException("closed"));
        verify(callback, never()).onError(any());
    }

    /** release→scheduler.shutdownNow。 */
    @Test
    public void release_shutsDownScheduler() {
        service.release();
        verify(scheduler, times(1)).shutdownNow();
    }

    // ---- 辅助：构造响应 JSON ----

    private void startTurn(String text) {
        service.startTurn("conversation-1", ++nextTurnId, text);
    }

    private static String deltaMessage(String delta, String msgId, int seq) {
        JsonObject payload = new JsonObject();
        payload.addProperty("delta", delta);
        payload.addProperty("full", delta);
        payload.addProperty("msgId", msgId);
        JsonObject root = new JsonObject();
        root.addProperty("event", ChatConfig.EVENT_STREAM_DELTA);
        root.add("payload", payload);
        root.addProperty("seq", seq);
        root.addProperty("type", "event");
        return root.toString();
    }

    private static String streamEndMessage() {
        JsonObject root = new JsonObject();
        root.addProperty("event", ChatConfig.EVENT_STREAM_END);
        root.addProperty("payload", "");
        root.addProperty("seq", 0);
        root.addProperty("type", "event");
        return root.toString();
    }
}
