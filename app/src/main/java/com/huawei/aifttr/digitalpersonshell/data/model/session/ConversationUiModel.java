package com.huawei.aifttr.digitalpersonshell.data.model.session;

/** 不可变 UI 快照；UI 不再从零散回调推断会话状态。 */
public final class ConversationUiModel {
    private final boolean visible;
    private final ConversationPhase phase;
    private final String userText;
    private final String assistantText;

    public ConversationUiModel(boolean visible, ConversationPhase phase,
                               String userText, String assistantText) {
        this.visible = visible;
        this.phase = phase;
        this.userText = userText == null ? "" : userText;
        this.assistantText = assistantText == null ? "" : assistantText;
    }

    public boolean isVisible() {
        return visible;
    }

    public ConversationPhase getPhase() {
        return phase;
    }

    public String getUserText() {
        return userText;
    }

    public String getAssistantText() {
        return assistantText;
    }
}
