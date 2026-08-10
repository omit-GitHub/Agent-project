package com.huawei.aifttr.digitalpersonshell.services;

import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceConfig;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationUiModel;
import com.huawei.aifttr.digitalpersonshell.data.model.session.VoiceSession;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.BubbleUiCallback;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.ChatCallback;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.utils.MarkdownText;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.util.ArrayDeque;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;

/**
 * 语音会话协调器。
 * <p>所有 Wakeup/ASR/WS/TTS 事件经 {@link SerialEventDispatcher} 串行处理；本类是
 * conversationId、阶段、TTS 队列和连续会话定时器的唯一所有者。</p>
 */
public class VoiceGateway implements ChatCallback {
    private static final String TAG = VoiceGateway.class.getSimpleName();
    private static final String GREETING_TTS_PREFIX = "wakeup-greeting";
    private static final String CHAT_ERROR_TTS_PREFIX = "chat-error";

    private final IVoiceService voiceService;
    private final VoiceSession session;
    private final SerialEventDispatcher events = new SerialEventDispatcher();
    private final ScheduledExecutorService sessionScheduler;
    private final boolean ownsSessionScheduler;
    private final ArrayDeque<DeltaItem> ttsQueue = new ArrayDeque<>();
    private final StringBuilder assistantText = new StringBuilder();

    private WebSocketChatService chatService;
    private BubbleUiCallback bubbleCallback;
    private String conversationId;
    private String userText = "";
    private long conversationEpoch;
    private long turnId;
    private long ttsSequence;
    private long activeAsrId = -1L;
    private String activeGreetingId;
    private String activeTtsId;
    private boolean ttsBusy;
    private boolean pendingStreamEnd;
    private boolean errorTtsActive;
    private boolean bargeInArmed;
    private boolean suppressWakePhrase;
    private ScheduledFuture<?> sessionTimeoutTask;

    public VoiceGateway(IVoiceService voiceService, VoiceSession session) {
        this(voiceService, session, null, null);
    }

    public VoiceGateway(IVoiceService voiceService, VoiceSession session,
                        WebSocketChatService chatService) {
        this(voiceService, session, chatService, null);
    }

    VoiceGateway(IVoiceService voiceService, VoiceSession session,
                 WebSocketChatService chatService, ScheduledExecutorService scheduler) {
        this.voiceService = voiceService;
        this.session = session;
        this.chatService = chatService;
        if (scheduler == null) {
            ThreadFactory daemonFactory = runnable -> {
                Thread thread = new Thread(runnable, "voice-session-timeout");
                thread.setDaemon(true);
                return thread;
            };
            this.sessionScheduler = Executors.newSingleThreadScheduledExecutor(daemonFactory);
            this.ownsSessionScheduler = true;
        } else {
            this.sessionScheduler = scheduler;
            this.ownsSessionScheduler = false;
        }
        registerListeners();
    }

    public void setChatService(WebSocketChatService chatService) {
        events.dispatch(() -> this.chatService = chatService);
    }

    public void setBubbleCallback(BubbleUiCallback bubbleCallback) {
        events.dispatch(() -> {
            this.bubbleCallback = bubbleCallback;
            renderUi();
        });
    }

    private void registerListeners() {
        voiceService.setWakeupListener((confidence, word) ->
                events.dispatch(() -> handleWakeup(confidence, word)));
        voiceService.setASRListener(new IVoiceService.ASRListener() {
            @Override
            public void onASRSpeechStart(long asrId) {
                events.dispatch(() -> handleAsrSpeechStart(asrId));
            }

            @Override
            public void onASRResult(long asrId, String words, byte[] audio, boolean isFinished) {
                events.dispatch(() -> handleAsrResult(asrId, words, audio, isFinished));
            }

            @Override
            public void onASRError(long asrId, int errorCode, String errorInfo) {
                events.dispatch(() -> handleAsrError(asrId, errorCode, errorInfo));
            }
        });
        voiceService.setTTSListener(new IVoiceService.TTSListener() {
            @Override
            public void onTTSProgress() {
            }

            @Override
            public void onTTSComplete(String id) {
                events.dispatch(() -> handleTtsComplete(id));
            }

            @Override
            public void onTTSError(String id) {
                events.dispatch(() -> handleTtsError(id));
            }
        });
        voiceService.setBargeInListener(asrId -> events.dispatch(() -> handleBargeIn(asrId)));
    }

    private void handleAsrSpeechStart(long asrId) {
        if (asrId == activeAsrId && session.getPhase() == ConversationPhase.LISTENING) {
            cancelSessionTimeout();
        }
    }

    private void handleWakeup(double confidence, String wakeupWord) {
        Logger.info(TAG, "[VOICE] wake epoch=" + (conversationEpoch + 1) + " word=" + wakeupWord);
        cancelSessionTimeout();
        voiceService.stopBargeInDetection();
        boolean hadOutput = ttsBusy || activeTtsId != null || activeGreetingId != null;
        invalidateOutput();
        if (chatService != null) {
            chatService.cancelChat();
        }
        if (hadOutput) {
            voiceService.cancelTTS();
            session.cancelTts();
        }

        conversationEpoch++;
        turnId = 0;
        conversationId = UUID.randomUUID().toString();
        session.beginConversation(conversationId, wakeupWord);
        suppressWakePhrase = true;
        userText = "";
        assistantText.setLength(0);
        renderUi();

        activeAsrId = voiceService.startASR();
        activeGreetingId = GREETING_TTS_PREFIX + "#" + conversationEpoch;
        voiceService.startTTS(VoiceConfig.GREETING_TEXT, activeGreetingId,
                VoiceConfig.DEFAULT_TTS_SPEED);
    }

    private void handleAsrResult(long asrId, String words, byte[] audio, boolean isFinished) {
        if (asrId != activeAsrId) {
            Logger.info(TAG, "[VOICE] ignore stale ASR result id=" + asrId + " active=" + activeAsrId);
            return;
        }
        if (session.getPhase() != ConversationPhase.LISTENING) {
            Logger.warn(TAG, "[VOICE] ignore ASR outside LISTENING phase=" + session.getPhase());
            return;
        }
        if (suppressWakePhrase) {
            String filtered = filterWakePhrase(words);
            if (filtered.isEmpty()) {
                if (isFinished) {
                    session.onContinueAsr();
                    activeAsrId = voiceService.startASR();
                }
                return;
            }
            words = filtered;
            suppressWakePhrase = false;
        }
        if (words == null || words.trim().isEmpty()) {
            if (isFinished && conversationId != null) {
                session.onContinueAsr();
                activeAsrId = voiceService.startASR();
                armSessionTimeout();
            }
            return;
        }

        cancelSessionTimeout();
        userText = words;
        session.onAsrResult(words, audio, isFinished);
        renderUi();
        if (!isFinished || chatService == null) {
            return;
        }
        turnId++;
        assistantText.setLength(0);
        session.onStartChat();
        renderUi();
        chatService.startTurn(conversationId, turnId, words);
    }

    private void handleAsrError(long asrId, int errorCode, String errorInfo) {
        if (asrId != activeAsrId) {
            Logger.info(TAG, "[VOICE] ignore stale ASR error id=" + asrId + " active=" + activeAsrId);
            return;
        }
        if (session.getPhase() != ConversationPhase.LISTENING) {
            return;
        }
        if (errorCode == VoiceConfig.ASR_TIMEOUT_ERROR_CODE && conversationId != null) {
            session.onContinueAsr();
            activeAsrId = voiceService.startASR();
            if (sessionTimeoutTask == null) {
                armSessionTimeout();
            }
            return;
        }
        endConversation("asr-error:" + errorCode);
    }

    private void handleTtsComplete(String id) {
        if (id != null && id.equals(activeGreetingId)) {
            activeGreetingId = null;
            if (session.getPhase() == ConversationPhase.LISTENING) {
                armSessionTimeout();
            }
            return;
        }
        if (id == null || !id.equals(activeTtsId)) {
            Logger.info(TAG, "[VOICE] ignore stale TTS complete id=" + id);
            return;
        }
        activeTtsId = null;
        ttsBusy = false;
        if (errorTtsActive) {
            errorTtsActive = false;
            disarmBargeIn();
            enterContinuousListening();
            return;
        }
        drainTtsQueue();
    }

    private void handleTtsError(String id) {
        if (id != null && id.equals(activeGreetingId)) {
            activeGreetingId = null;
            if (session.getPhase() == ConversationPhase.LISTENING) {
                armSessionTimeout();
            }
            return;
        }
        if (id == null || !id.equals(activeTtsId)) {
            return;
        }
        activeTtsId = null;
        ttsBusy = false;
        if (errorTtsActive) {
            errorTtsActive = false;
            disarmBargeIn();
            enterContinuousListening();
            return;
        }
        drainTtsQueue();
    }

    private void handleBargeIn(long asrId) {
        if (!bargeInArmed || session.getPhase() != ConversationPhase.SPEAKING) {
            return;
        }
        Logger.info(TAG, "[VOICE] barge-in conversation=" + conversationId + " turn=" + turnId);
        if (chatService != null) {
            chatService.cancelChat();
        }
        invalidateOutput();
        voiceService.cancelTTS();
        cancelSessionTimeout();
        activeAsrId = asrId;
        session.cancelTts();
        session.onContinueAsr();
        assistantText.setLength(0);
        renderUi();
        // VoiceServiceManager 保留同一录音流并在回调返回后启动 ASR。
    }

    @Override
    public void onDelta(String delta, String msgId) {
        events.dispatch(() -> handleDelta(delta, msgId));
    }

    private void handleDelta(String delta, String msgId) {
        if (session.getPhase() != ConversationPhase.THINKING
                && session.getPhase() != ConversationPhase.SPEAKING) {
            return;
        }
        ttsQueue.addLast(new DeltaItem(MarkdownText.stripBold(delta), msgId));
        assistantText.append(delta);
        session.onAssistantDelta();
        renderUi();
        if (!ttsBusy) {
            drainTtsQueue();
        }
    }

    @Override
    public void onStreamEnd() {
        events.dispatch(this::handleStreamEnd);
    }

    private void handleStreamEnd() {
        if (session.getPhase() != ConversationPhase.THINKING
                && session.getPhase() != ConversationPhase.SPEAKING) {
            return;
        }
        if (ttsBusy || !ttsQueue.isEmpty()) {
            pendingStreamEnd = true;
            return;
        }
        enterContinuousListening();
    }

    @Override
    public void onError(String msg) {
        events.dispatch(() -> handleChatError(msg));
    }

    private void handleChatError(String msg) {
        if (session.getPhase() != ConversationPhase.THINKING
                && session.getPhase() != ConversationPhase.SPEAKING) {
            return;
        }
        Logger.error(TAG, "[VOICE] chat error=" + msg);
        voiceService.stopBargeInDetection();
        if (ttsBusy || activeTtsId != null) {
            voiceService.cancelTTS();
        }
        invalidateOutput();
        session.onChatError();
        assistantText.setLength(0);
        assistantText.append(ChatConfig.ERROR_FALLBACK_TEXT);
        errorTtsActive = true;
        ttsBusy = true;
        activeTtsId = nextTtsId(CHAT_ERROR_TTS_PREFIX);
        session.onStartTts(activeTtsId);
        armBargeIn();
        renderUi();
        voiceService.startTTS(ChatConfig.ERROR_FALLBACK_TEXT, activeTtsId,
                VoiceConfig.DEFAULT_TTS_SPEED);
    }

    private void drainTtsQueue() {
        DeltaItem item = ttsQueue.pollFirst();
        if (item != null) {
            ttsBusy = true;
            activeTtsId = nextTtsId(item.id);
            session.onStartTts(activeTtsId);
            armBargeIn();
            voiceService.startTTS(item.text, activeTtsId, VoiceConfig.DEFAULT_TTS_SPEED);
            return;
        }
        if (pendingStreamEnd) {
            pendingStreamEnd = false;
            enterContinuousListening();
        }
    }

    private void enterContinuousListening() {
        disarmBargeIn();
        ttsBusy = false;
        activeTtsId = null;
        pendingStreamEnd = false;
        errorTtsActive = false;
        session.onStreamEnd();
        session.onContinueAsr();
        renderUi();
        activeAsrId = voiceService.startASR();
        armSessionTimeout();
    }

    private void armSessionTimeout() {
        cancelSessionTimeout();
        if (conversationId == null || session.getPhase() != ConversationPhase.LISTENING) {
            return;
        }
        long expectedEpoch = conversationEpoch;
        sessionTimeoutTask = sessionScheduler.schedule(
                () -> events.dispatch(() -> handleSessionTimeout(expectedEpoch)),
                VoiceConfig.CONTINUOUS_SESSION_TIMEOUT_MS, TimeUnit.MILLISECONDS);
    }

    private void handleSessionTimeout(long expectedEpoch) {
        sessionTimeoutTask = null;
        if (expectedEpoch != conversationEpoch
                || session.getPhase() != ConversationPhase.LISTENING) {
            return;
        }
        endConversation("idle-timeout");
    }

    private void endConversation(String reason) {
        Logger.info(TAG, "[VOICE] end conversation reason=" + reason + " id=" + conversationId);
        cancelSessionTimeout();
        voiceService.stopBargeInDetection();
        voiceService.stopASR();
        activeAsrId = -1L;
        if (chatService != null) {
            chatService.cancelChat();
        }
        invalidateOutput();
        conversationId = null;
        session.endConversation();
        userText = "";
        assistantText.setLength(0);
        renderUi();
    }

    private void cancelSessionTimeout() {
        if (sessionTimeoutTask != null) {
            sessionTimeoutTask.cancel(false);
            sessionTimeoutTask = null;
        }
    }

    private void renderUi() {
        if (bubbleCallback == null) {
            return;
        }
        bubbleCallback.render(new ConversationUiModel(
                session.getPhase() != ConversationPhase.WAITING_WAKE,
                session.getPhase(), userText, assistantText.toString()));
    }

    private void armBargeIn() {
        if (!bargeInArmed) {
            bargeInArmed = voiceService.startBargeInDetection();
        }
    }

    private void disarmBargeIn() {
        if (bargeInArmed) {
            bargeInArmed = false;
            voiceService.stopBargeInDetection();
        }
    }

    private void invalidateOutput() {
        bargeInArmed = false;
        ttsBusy = false;
        activeTtsId = null;
        activeGreetingId = null;
        pendingStreamEnd = false;
        errorTtsActive = false;
        ttsQueue.clear();
    }

    private String nextTtsId(String sourceId) {
        return sourceId + "#e" + conversationEpoch + "-t" + turnId + "-s" + (++ttsSequence);
    }

    private String filterWakePhrase(String words) {
        if (words == null) {
            return "";
        }
        String value = words.trim();
        if (value.startsWith(VoiceConfig.DEFAULT_WAKEUP_WORD)) {
            return value.substring(VoiceConfig.DEFAULT_WAKEUP_WORD.length())
                    .replaceFirst("^[,，。.!！?？\\s]+", "").trim();
        }
        if (VoiceConfig.DEFAULT_WAKEUP_WORD.startsWith(value)) {
            return "";
        }
        String compact = value.toLowerCase(java.util.Locale.ROOT).replaceAll("\\s+", "");
        return "nihaoxiaoguang".startsWith(compact) ? "" : value;
    }

    public void release() {
        events.dispatch(() -> {
            cancelSessionTimeout();
            if (ownsSessionScheduler) {
                sessionScheduler.shutdownNow();
            }
        });
    }

    private static final class DeltaItem {
        final String text;
        final String id;

        DeltaItem(String text, String id) {
            this.text = text;
            this.id = id == null ? "delta" : id;
        }
    }
}
