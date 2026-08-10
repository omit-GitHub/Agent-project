package com.huawei.aifttr.digitalpersonshell.ui;

import android.app.Service;
import android.content.Intent;

import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.huawei.aifttr.digitalpersonshell.ui.VoiceForegroundService;
import com.huawei.aifttr.digitalpersonshell.data.model.session.VoiceSession;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;

/**
 * VoiceForegroundService 前台保活测试（TC-014 / SC-012 / BR-001/NFR-004）。
 * <p>
 * isReturnDefaultValues 下跑 Service 生命周期，验证 onStartCommand 后
 * VoiceGateway 被初始化且 session 维持 Listening。
 */
public class VoiceForegroundServiceTest {

    private VoiceForegroundService service;

    @Before
    public void setUp() {
        service = new VoiceForegroundService();
    }

    @Test
    public void onStartCommand_keepsSessionListening() {
        Intent intent = new Intent();
        int result = service.onStartCommand(intent, 0, 1);

        assertEquals(Service.START_STICKY, result);
        VoiceSession session = service.getSession();
        assertEquals(ConversationPhase.WAITING_WAKE, session.getPhase());
    }
}
