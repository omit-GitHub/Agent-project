package com.huawei.aifttr.digitalpersonshell.services;

import org.junit.Before;
import org.junit.Test;
import org.mockito.ArgumentCaptor;

import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

import com.huawei.aifttr.digitalpersonshell.constants.ChatConfig;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationUiModel;
import com.huawei.aifttr.digitalpersonshell.data.model.session.VoiceSession;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.BubbleUiCallback;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyFloat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public class VoiceGatewayTest {
    private Harness h;

    @Before
    public void setUp() {
        h = new Harness();
    }

    @Test
    public void wakeup_createsConversationStartsAsrAndUniqueGreeting() {
        h.wake.onWakeup(0.9, "你好小光");

        assertTrue(h.session.getSessionId() != null && !h.session.getSessionId().isEmpty());
        assertEquals(ConversationPhase.LISTENING, h.session.getPhase());
        verify(h.voice).startASR();
        verify(h.voice).startTTS("我在", "wakeup-greeting#1", 1.0f);
    }

    @Test
    public void finalAsr_startsTurnWithCoordinatorConversationId() {
        h.wake.onWakeup(0.9, "你好小光");
        String conversationId = h.session.getSessionId();
        h.asr.onASRResult(1L, "打开空调", null, true);

        verify(h.chat).startTurn(conversationId, 1L, "打开空调");
        assertEquals(ConversationPhase.THINKING, h.session.getPhase());
    }

    @Test
    public void staleAsrResult_isIgnored() {
        h.wake.onWakeup(0.9, "你好小光");
        h.asr.onASRResult(99L, "旧问题", null, true);

        verify(h.chat, never()).startTurn(anyString(), anyLong(), anyString());
        assertNull(h.session.getLastAsrText());
    }

    @Test
    public void wakePhrase_isNotSentToAgent() {
        h.wake.onWakeup(0.9, "你好小光");
        h.asr.onASRResult(1L, "你好小光", null, true);

        verify(h.chat, never()).startTurn(anyString(), anyLong(), anyString());
        verify(h.voice, times(2)).startASR();
    }

    @Test
    public void wakePrefixedCommand_stripsWakePhrase() {
        h.wake.onWakeup(0.9, "你好小光");
        h.asr.onASRResult(1L, "你好小光，打开空调", null, true);

        verify(h.chat).startTurn(eq(h.session.getSessionId()), eq(1L), eq("打开空调"));
    }

    @Test
    public void deltas_areQueuedAndPlayedWithUniqueIds() {
        h.startTurn();
        h.gateway.onDelta("第一段", "msg-1");
        h.gateway.onDelta("第二段", "msg-2");

        verify(h.voice).startTTS("第一段", "msg-1#e1-t1-s1", 1.0f);
        verify(h.voice, never()).startTTS(eq("第二段"), anyString(), anyFloat());
        h.tts.onTTSComplete("msg-1#e1-t1-s1");
        verify(h.voice).startTTS("第二段", "msg-2#e1-t1-s2", 1.0f);
    }

    @Test
    public void streamEnd_waitsForTtsThenStartsListening() {
        h.startTurn();
        h.gateway.onDelta("回答", "msg");
        h.gateway.onStreamEnd();
        h.tts.onTTSComplete("msg#e1-t1-s1");

        assertEquals(ConversationPhase.LISTENING, h.session.getPhase());
        verify(h.voice, times(2)).startASR();
        verify(h.scheduler).schedule(any(Runnable.class), eq(10_000L), eq(TimeUnit.MILLISECONDS));
    }

    @Test
    public void sessionTimeout_isIndependentOfAsrError() {
        h.wake.onWakeup(0.9, "你好小光");
        h.tts.onTTSComplete("wakeup-greeting#1");
        h.timeoutRunnable.getValue().run();

        assertNull(h.session.getSessionId());
        assertEquals(ConversationPhase.WAITING_WAKE, h.session.getPhase());
        verify(h.voice).stopASR();
    }

    @Test
    public void validPartial_cancelsSessionTimeout() {
        h.wake.onWakeup(0.9, "你好小光");
        h.tts.onTTSComplete("wakeup-greeting#1");
        h.asr.onASRResult(1L, "打开", null, false);

        verify(h.timeoutFuture).cancel(false);
    }

    @Test
    public void speechBeginningAtDeadline_cancelsSessionTimeoutBeforePartial() {
        h.wake.onWakeup(0.9, "你好小光");
        h.tts.onTTSComplete("wakeup-greeting#1");
        h.asr.onASRSpeechStart(1L);

        verify(h.timeoutFuture).cancel(false);
    }

    @Test
    public void oldGreetingCallback_doesNotArmNewConversationTimer() {
        h.wake.onWakeup(0.9, "你好小光");
        String first = h.session.getSessionId();
        h.wake.onWakeup(0.9, "你好小光");
        String second = h.session.getSessionId();
        h.tts.onTTSComplete("wakeup-greeting#1");

        assertNotEquals(first, second);
        verify(h.scheduler, never()).schedule(any(Runnable.class), anyLong(), any(TimeUnit.class));
    }

    @Test
    public void bargeIn_keepsConversationAndAcceptsTransferredAsrId() {
        h.startTurn();
        String conversationId = h.session.getSessionId();
        h.gateway.onDelta("旧回答", "msg");
        h.barge.onBargeIn(77L);
        h.asr.onASRResult(77L, "继续说", null, true);

        verify(h.voice).cancelTTS();
        verify(h.chat).startTurn(conversationId, 2L, "继续说");
    }

    @Test
    public void chatError_usesFallbackAndRemainsInterruptible() {
        h.startTurn();
        h.gateway.onError("network");

        verify(h.voice).startTTS(eq(ChatConfig.ERROR_FALLBACK_TEXT),
                eq("chat-error#e1-t1-s1"), anyFloat());
        h.barge.onBargeIn(88L);
        verify(h.voice).cancelTTS();
    }

    @Test
    public void uiReceivesCompleteSnapshots() {
        BubbleUiCallback ui = mock(BubbleUiCallback.class);
        h.gateway.setBubbleCallback(ui);
        h.wake.onWakeup(0.9, "你好小光");
        h.asr.onASRResult(1L, "讲故事", null, true);
        h.gateway.onDelta("好的", "msg");

        ArgumentCaptor<ConversationUiModel> models = ArgumentCaptor.forClass(ConversationUiModel.class);
        verify(ui, times(5)).render(models.capture());
        ConversationUiModel latest = models.getValue();
        assertEquals(ConversationPhase.SPEAKING, latest.getPhase());
        assertEquals("讲故事", latest.getUserText());
        assertEquals("好的", latest.getAssistantText());
    }

    private static final class Harness {
        final IVoiceService voice = mock(IVoiceService.class);
        final WebSocketChatService chat = mock(WebSocketChatService.class);
        final ScheduledExecutorService scheduler = mock(ScheduledExecutorService.class);
        final ScheduledFuture<Object> timeoutFuture = mock(ScheduledFuture.class);
        final VoiceSession session = new VoiceSession();
        final ArgumentCaptor<Runnable> timeoutRunnable = ArgumentCaptor.forClass(Runnable.class);
        final VoiceGateway gateway;
        final IVoiceService.WakeupListener wake;
        final IVoiceService.ASRListener asr;
        final IVoiceService.TTSListener tts;
        final IVoiceService.BargeInListener barge;

        Harness() {
            when(voice.startASR()).thenReturn(1L, 2L, 3L, 4L);
            when(voice.startBargeInDetection()).thenReturn(true);
            doReturn(timeoutFuture).when(scheduler)
                    .schedule(timeoutRunnable.capture(), anyLong(), eq(TimeUnit.MILLISECONDS));
            session.onInitSuccess();
            gateway = new VoiceGateway(voice, session, chat, scheduler);

            ArgumentCaptor<IVoiceService.WakeupListener> wakeCaptor =
                    ArgumentCaptor.forClass(IVoiceService.WakeupListener.class);
            ArgumentCaptor<IVoiceService.ASRListener> asrCaptor =
                    ArgumentCaptor.forClass(IVoiceService.ASRListener.class);
            ArgumentCaptor<IVoiceService.TTSListener> ttsCaptor =
                    ArgumentCaptor.forClass(IVoiceService.TTSListener.class);
            ArgumentCaptor<IVoiceService.BargeInListener> bargeCaptor =
                    ArgumentCaptor.forClass(IVoiceService.BargeInListener.class);
            verify(voice).setWakeupListener(wakeCaptor.capture());
            verify(voice).setASRListener(asrCaptor.capture());
            verify(voice).setTTSListener(ttsCaptor.capture());
            verify(voice).setBargeInListener(bargeCaptor.capture());
            wake = wakeCaptor.getValue();
            asr = asrCaptor.getValue();
            tts = ttsCaptor.getValue();
            barge = bargeCaptor.getValue();
        }

        void startTurn() {
            wake.onWakeup(0.9, "你好小光");
            asr.onASRResult(1L, "问题", null, true);
        }
    }
}
