package com.huawei.aifttr.digitalpersonshell.data.model.session;

/**
 * 当前语音 conversation 的只读快照。
 * <p>所有写入由 VoiceGateway 的串行事件流完成，phase 是唯一会话状态。</p>
 */
public class VoiceSession {
    private String sessionId;
    private ConversationPhase phase = ConversationPhase.WAITING_WAKE;
    private String lastWakeupWord;
    private String lastAsrText;
    private String ttsId;

    public ConversationPhase getPhase() {
        return phase;
    }

    public String getLastWakeupWord() {
        return lastWakeupWord;
    }

    public String getLastAsrText() {
        return lastAsrText;
    }

    public String getTtsId() {
        return ttsId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public void onInitSuccess() {
        phase = ConversationPhase.WAITING_WAKE;
    }

    public void beginConversation(String sessionId, String wakeupWord) {
        this.sessionId = sessionId;
        this.lastWakeupWord = wakeupWord;
        this.lastAsrText = null;
        this.ttsId = null;
        this.phase = ConversationPhase.LISTENING;
    }

    public void endConversation() {
        sessionId = null;
        ttsId = null;
        phase = ConversationPhase.WAITING_WAKE;
    }

    public void onAsrResult(String words, byte[] audio, boolean isFinished) {
        lastAsrText = words;
        if (isFinished) {
            phase = ConversationPhase.THINKING;
        }
    }

    public void onStartChat() {
        phase = ConversationPhase.THINKING;
    }

    public void onContinueAsr() {
        phase = ConversationPhase.LISTENING;
    }

    public void onStreamEnd() {
        ttsId = null;
        phase = ConversationPhase.LISTENING;
    }

    public void onChatError() {
        ttsId = null;
        phase = ConversationPhase.SPEAKING;
    }

    public void onStartTts(String ttsId) {
        this.ttsId = ttsId;
        phase = ConversationPhase.SPEAKING;
    }

    public void onAssistantDelta() {
        phase = ConversationPhase.SPEAKING;
    }

    public void cancelTts() {
        ttsId = null;
        phase = sessionId == null ? ConversationPhase.WAITING_WAKE : ConversationPhase.LISTENING;
    }
}
