package com.huawei.aifttr.digitalpersonshell.services;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;
import com.huawei.aifttr.digitalpersonshell.data.model.entities.chat.ChatRequest;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatCallback;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatSocketListener;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IpSupplier;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketConnection;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketFactory;
import com.huawei.aifttr.digitalpersonshell.utils.IpUtils;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * WebSocket 对话服务核心（T-WS-05）。
 * <p>
 * 每轮对话新建连接；conversationId 由上层会话协调器提供，
 * 建链 {@code ws://<ip>:17000/ws?sessionId=<uuid>}，使 Agent 端按稳定 ChatKey 承接多轮上下文；
 * onOpen 后发送 {@code chat.send}（id 与 sessionId 一致）；接收 stream.delta→onDelta 送 TTS，
 * stream_end→onStreamEnd 结束本轮；传输超时后兜底且不重连（直接 onError 播报兜底语）；
 * 支持 cancelChat 打断。
 * <p>
 * 经端口 {@link WebSocketFactory}/{@link IpSupplier}/{@link ScheduledExecutorService} 注入，
 * 纯 JVM 单测可捕获 {@link ChatSocketListener} 后手动触发，无真实网络/线程。
 *
 * @see ChatCallback
 */
public class WebSocketChatService {

    private static final String TAG = "WebSocketChatService";
    private static final String FALLBACK_IP = "0.0.0.0";

    private final IpSupplier ipSupplier;
    private final WebSocketFactory factory;
    private final ScheduledExecutorService scheduler;
    private final ChatCallback callback;

    private final Object lock = new Object();
    private volatile WebSocketConnection connection;
    private volatile boolean isChatting = false;
    private volatile ScheduledFuture<?> timeoutTask;
    /** 当前传输使用的 Agent conversation；所有权在 VoiceGateway。 */
    private String conversationId;
    private String chatText;
    /** 本地传输代数；每次 start/cancel 都递增以隔离迟到 socket 回调。 */
    private long transportGeneration = 0;

    public WebSocketChatService(IpSupplier ipSupplier, WebSocketFactory factory,
                               ScheduledExecutorService scheduler, ChatCallback callback) {
        this.ipSupplier = ipSupplier;
        this.factory = factory;
        this.scheduler = scheduler;
        this.callback = callback;
    }

    /**
     * 拼装 WebSocket URL：ws://<ip>:17000/ws?sessionId=<sessionId>。
     */
    public static String buildUrl(String ip, String sessionId) {
        return ChatConfig.WS_SCHEME + ip + ":" + ChatConfig.WS_PORT + ChatConfig.WS_PATH + sessionId;
    }

    /**
     * 发起一轮对话。
     *
     * @param text ASR 最终拾音文本
     */
    public void startTurn(String conversationId, long turnId, String text) {
        synchronized (lock) {
            isChatting = false;
            transportGeneration++;
            cancelTimeoutTask();
            cancelCurrentConnection();
            if (conversationId == null || conversationId.trim().isEmpty()) {
                throw new IllegalArgumentException("conversationId is required");
            }
            this.conversationId = conversationId;
            this.chatText = text;
            this.isChatting = true;
            openConnection(resolveIp(), transportGeneration);
            Logger.info(TAG, "[CHAT] startTurn conversationId=" + conversationId + " turnId=" + turnId);
        }
    }

    private void openConnection(String ip, long roundId) {
        String url = buildUrl(ip, conversationId);
        connection = factory.open(url, createListener(roundId));
        startTimeoutTask(roundId);
    }

    private ChatSocketListener createListener(long roundId) {
        return new ChatSocketListener() {
            @Override
            public void onOpen() {
                WebSocketChatService.this.onOpen(roundId);
            }

            @Override
            public void onMessage(String data) {
                WebSocketChatService.this.onMessage(roundId, data);
            }

            @Override
            public void onFailure(Throwable t) {
                WebSocketChatService.this.onFailure(roundId, t);
            }

            @Override
            public void onClosed(int code, String reason) {
                WebSocketChatService.this.onClosed(roundId, code, reason);
            }
        };
    }

    void onOpen(long roundId) {
        synchronized (lock) {
            if (!isCurrentRound(roundId)) {
                return;
            }
            String message = new ChatRequest(conversationId, chatText).toJson();
            Logger.info(TAG, "[CHAT] onOpen send: " + message);
            if (connection != null) {
                connection.send(message);
            }
            startTimeoutTask(roundId);
        }
    }

    void onMessage(long roundId, String data) {
        synchronized (lock) {
            if (!isCurrentRound(roundId)) {
                Logger.warn(TAG, "[CHAT] ignore stale message roundId=" + roundId);
                return;
            }
            Logger.info(TAG, "[CHAT] RECV raw: " + data);
            processMessage(data);
            // 每帧重置超时；流中途停顿超过阈值仍能回调上层复位。
            if (isCurrentRound(roundId)) {
                startTimeoutTask(roundId);
            }
        }
    }

    private void processMessage(String data) {
        if (data == null || data.isEmpty()) {
            Logger.warn(TAG, "[CHAT] empty message, ignore");
            return;
        }
        try {
            JsonObject obj = JsonParser.parseString(data).getAsJsonObject();
            String event = obj.has(ChatConfig.KEY_EVENT) ? obj.get(ChatConfig.KEY_EVENT).getAsString() : "";
            if (ChatConfig.EVENT_STREAM_DELTA.equals(event)) {
                JsonObject payload =
                        obj.has(ChatConfig.KEY_PAYLOAD) ? obj.getAsJsonObject(ChatConfig.KEY_PAYLOAD) : new JsonObject();
                String delta = payload.has(ChatConfig.KEY_DELTA) ? payload.get(ChatConfig.KEY_DELTA).getAsString() : "";
                String msgId = payload.has(ChatConfig.KEY_MSG_ID) ? payload.get(ChatConfig.KEY_MSG_ID).getAsString() : "";
                callback.onDelta(delta, msgId);
            } else if (ChatConfig.EVENT_STREAM_END.equals(event)) {
                isChatting = false;
                cancelTimeoutTask();
                cancelCurrentConnection();
                callback.onStreamEnd();
            } else {
                Logger.warn(TAG, "[CHAT] unknown event: " + event);
            }
        } catch (Exception e) {
            Logger.error(TAG, "[CHAT] parse failed: " + data, e);
            isChatting = false;
            cancelTimeoutTask();
            cancelCurrentConnection();
            callback.onError(ChatConfig.ERROR_FALLBACK_TEXT);
        }
    }

    void onFailure(long roundId, Throwable t) {
        synchronized (lock) {
            // 对话已结束（stream_end 后）的正常断开，不上报、不重连
            if (!isCurrentRound(roundId)) {
                return;
            }
            Logger.error(TAG, "[CHAT] onFailure: " + t);
            terminateWithError("onFailure");
        }
    }

    void onClosed(long roundId, int code, String reason) {
        synchronized (lock) {
            if (!isCurrentRound(roundId)) {
                return;
            }
            Logger.info(TAG, "[CHAT] onClosed code=" + code + " reason=" + reason);
            // 未收到 stream_end 就关闭属于异常结束，必须通知 Gateway 复位 chatActive。
            terminateWithError("onClosed");
        }
    }

    private void handleTimeout(long roundId) {
        synchronized (lock) {
            if (!isCurrentRound(roundId)) {
                return;
            }
            Logger.warn(TAG, "[CHAT] timeout after " + ChatConfig.TIMEOUT_SECONDS + "s");
            terminateWithError("timeout");
        }
    }

    /**
     * 失败/超时统一处理：取消当前连接与超时，立即 onError 兜底（不重连）。
     * <p>
     * 一旦播报兜底语即不再重试，由会话协调器在兜底播报后恢复连续监听。
     */
    private void terminateWithError(String reason) {
        // 先置结束，防止 connection.cancel() 同步触发 onClosed/onFailure 时重入终止流程。
        isChatting = false;
        cancelCurrentConnection();
        cancelTimeoutTask();
        Logger.error(TAG, "[CHAT] terminate with error (" + reason + ")");
        callback.onError(ChatConfig.ERROR_FALLBACK_TEXT);
    }

    private String resolveIp() {
        return ipSupplier.get().map(IpUtils::setLastSegmentToOne).orElse(FALLBACK_IP);
    }

    private void startTimeoutTask(long roundId) {
        cancelTimeoutTask();
        timeoutTask = scheduler.schedule(() -> handleTimeout(roundId),
                ChatConfig.TIMEOUT_SECONDS, TimeUnit.SECONDS);
    }

    private boolean isCurrentRound(long roundId) {
        return isChatting && roundId == transportGeneration;
    }

    private void cancelTimeoutTask() {
        if (timeoutTask != null) {
            timeoutTask.cancel(true);
            timeoutTask = null;
        }
    }

    private void cancelCurrentConnection() {
        if (connection != null) {
            connection.cancel();
            connection = null;
        }
    }

    /**
     * 打断当前对话：取消连接 + 取消超时。用于唤醒打断。
     */
    public void cancelChat() {
        synchronized (lock) {
            isChatting = false;
            transportGeneration++;
            cancelCurrentConnection();
            cancelTimeoutTask();
        }
    }

    /**
     * 释放资源。
     */
    public void release() {
        synchronized (lock) {
            isChatting = false;
            transportGeneration++;
            cancelCurrentConnection();
            cancelTimeoutTask();
        }
        scheduler.shutdownNow();
    }
}
