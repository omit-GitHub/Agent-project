package com.huawei.aifttr.digitalpersonshell.ui.bubble;

import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationUiModel;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.BubbleUiCallback;

/** 将协调器的完整 UI 快照映射到 Android 视图。 */
public class ChatBubblePresenter implements BubbleUiCallback {
    private final IBubbleView view;

    public ChatBubblePresenter(IBubbleView view) {
        this.view = view;
    }

    @Override
    public void render(ConversationUiModel model) {
        if (!model.isVisible()) {
            view.hidePanel();
            return;
        }
        view.showPanel();
        view.setVoiceState(model.getPhase());
        view.setUserText(model.getUserText());
        view.setSystemText(model.getAssistantText());
    }
}
