package com.huawei.aifttr.digitalpersonshell.data.model.session;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

public class VoiceSessionTest {
    @Test
    public void beginConversation_ownsIdAndListens() {
        VoiceSession session = new VoiceSession();
        session.beginConversation("session-1", "你好小光");

        assertEquals("session-1", session.getSessionId());
        assertEquals("你好小光", session.getLastWakeupWord());
        assertEquals(ConversationPhase.LISTENING, session.getPhase());
    }

    @Test
    public void finalAsr_entersThinking() {
        VoiceSession session = activeSession();
        session.onAsrResult("打开空调", null, true);

        assertEquals(ConversationPhase.THINKING, session.getPhase());
        assertEquals("打开空调", session.getLastAsrText());
    }

    @Test
    public void ttsAndContinuousListening_haveSinglePhase() {
        VoiceSession session = activeSession();
        session.onStartTts("tts-1");
        assertEquals(ConversationPhase.SPEAKING, session.getPhase());

        session.onStreamEnd();
        assertEquals(ConversationPhase.LISTENING, session.getPhase());
        assertNull(session.getTtsId());
    }

    @Test
    public void endConversation_clearsIdAndWaitsForWake() {
        VoiceSession session = activeSession();
        session.endConversation();

        assertNull(session.getSessionId());
        assertEquals(ConversationPhase.WAITING_WAKE, session.getPhase());
    }

    private static VoiceSession activeSession() {
        VoiceSession session = new VoiceSession();
        session.beginConversation("session-1", "你好小光");
        return session;
    }
}
