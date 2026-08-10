package com.huawei.aifttr.digitalpersonshell.ui.bubble;

import org.junit.Before;
import org.junit.Test;

import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationUiModel;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

public class ChatBubblePresenterTest {
    private IBubbleView view;
    private ChatBubblePresenter presenter;

    @Before
    public void setUp() {
        view = mock(IBubbleView.class);
        presenter = new ChatBubblePresenter(view);
    }

    @Test
    public void visibleSnapshot_rendersAllFields() {
        presenter.render(new ConversationUiModel(true, ConversationPhase.LISTENING,
                "打开空调", "好的"));

        verify(view).showPanel();
        verify(view).setVoiceState(ConversationPhase.LISTENING);
        verify(view).setUserText("打开空调");
        verify(view).setSystemText("好的");
    }

    @Test
    public void subsequentSnapshot_isRenderedIdempotentlyByView() {
        presenter.render(new ConversationUiModel(true, ConversationPhase.LISTENING, "", ""));
        presenter.render(new ConversationUiModel(true, ConversationPhase.SPEAKING, "问题", "回答"));

        verify(view, org.mockito.Mockito.times(2)).showPanel();
        verify(view).setVoiceState(ConversationPhase.SPEAKING);
    }

    @Test
    public void hiddenSnapshot_hidesVisiblePanel() {
        presenter.render(new ConversationUiModel(true, ConversationPhase.LISTENING, "", ""));
        presenter.render(new ConversationUiModel(false, ConversationPhase.WAITING_WAKE, "", ""));

        verify(view).hidePanel();
    }

    @Test
    public void initiallyHiddenSnapshot_isNoOp() {
        presenter.render(new ConversationUiModel(false, ConversationPhase.WAITING_WAKE, "", ""));

        verify(view, never()).showPanel();
        verify(view).hidePanel();
    }
}
