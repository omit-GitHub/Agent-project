package com.huawei.aifttr.digitalpersonshell.services;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IASREngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ISpeechProvider;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ITTSEngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IVadEngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;
import com.huawei.aifttr.digitalpersonshell.services.VoiceServiceManager;

import org.junit.Before;
import org.junit.Test;
import org.mockito.ArgumentCaptor;

import android.content.Context;

import java.io.File;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * VoiceServiceManager 引擎编排测试（T-003 / TC-001/003/004 / BR-001/002/007）。
 * <p>
 * Mock ISpeechProvider，ArgumentCaptor 捕获授权回调与各引擎 init 注册的监听器，
 * 验证 4 引擎计数与成功/失败路由。声纹引擎不存在（BR-007）。
 */
public class VoiceServiceManagerTest {

    private ISpeechProvider speechProvider;
    private IVoiceService.InitCallback callback;
    private IASREngine asrEngine;
    private IWakeupEngine wakeupEngine;
    private IVadEngine vadEngine;
    private ITTSEngine ttsEngine;

    @Before
    public void setUp() {
        speechProvider = mock(ISpeechProvider.class);
        callback = mock(IVoiceService.InitCallback.class);
        asrEngine = mock(IASREngine.class);
        wakeupEngine = mock(IWakeupEngine.class);
        vadEngine = mock(IVadEngine.class);
        ttsEngine = mock(ITTSEngine.class);
    }

    /** TC-001 4 引擎 init 成功→onSuccess，计数==4（BR-001/007）。 */
    @Test
    public void init_allFourEnginesReady_onSuccess() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);

        // 授权成功后触发引擎构造
        fireAuthSuccess();
        verify(speechProvider, times(1)).getASREngine();
        verify(speechProvider, times(1)).getWakeupEngine();
        verify(speechProvider, times(1)).getVadEngine();
        verify(speechProvider, times(1)).getTTSEngine();
        verify(asrEngine).setWakeupEngine(wakeupEngine, VoiceServiceConstants.ASR_WAKEUP_WORD);

        // 4 引擎 init 成功
        fireEngineInit(asrEngine, IASREngine.ASRListener.class, 0);
        fireEngineInit(vadEngine, IVadEngine.VadListener.class, 0);
        fireEngineInit(wakeupEngine, IWakeupEngine.WakeupListener.class, 0);
        fireEngineInit(ttsEngine, ITTSEngine.TTSListener.class, 0);

        verify(callback, times(1)).onSuccess();
        assertEquals(4, manager.getEngineInitCount());
    }

    /** TC-003 授权失败→onError，不构造引擎（BR-002）。 */
    @Test
    public void init_authFailed_doesNotInitEngines() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);

        fireAuthError();
        verify(callback, times(1)).onError(org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.anyString());
        verify(speechProvider, never()).getASREngine();
        verify(speechProvider, never()).getWakeupEngine();
        verify(speechProvider, never()).getVadEngine();
        verify(speechProvider, never()).getTTSEngine();
    }

    /** TC-004 单引擎（Wakeup）init 失败→onError（BR-001/NFR-001）。 */
    @Test
    public void init_oneEngineFails_onError() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);
        fireAuthSuccess();

        fireEngineInit(asrEngine, IASREngine.ASRListener.class, 0);
        fireEngineInit(vadEngine, IVadEngine.VadListener.class, 0);
        fireEngineInit(ttsEngine, ITTSEngine.TTSListener.class, 0);
        // Wakeup init 失败（非 0 状态）
        fireEngineInit(wakeupEngine, IWakeupEngine.WakeupListener.class, 1);

        verify(callback, times(1)).onError(org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.anyString());
        verify(callback, never()).onSuccess();
    }

    /** 唤醒命中→转发到外部 WakeupListener（带 confidence），由监听器编排 ASR（BR-003 问候）。 */
    @Test
    public void onWakeup_forwardsToWakeupListener() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);
        fireAuthSuccess();
        fireEngineInit(asrEngine, IASREngine.ASRListener.class, 0);
        fireEngineInit(vadEngine, IVadEngine.VadListener.class, 0);
        fireEngineInit(wakeupEngine, IWakeupEngine.WakeupListener.class, 0);
        fireEngineInit(ttsEngine, ITTSEngine.TTSListener.class, 0);

        IVoiceService.WakeupListener external = mock(IVoiceService.WakeupListener.class);
        manager.setWakeupListener(external);

        // 捕获注册到唤醒引擎的监听器并触发 onWakeup
        ArgumentCaptor<IWakeupEngine.WakeupListener> captor =
                ArgumentCaptor.forClass(IWakeupEngine.WakeupListener.class);
        verify(wakeupEngine).init(org.mockito.ArgumentMatchers.any(), captor.capture());
        captor.getValue().onWakeup(0.9, "ni hao xiao guang");

        verify(external, times(1)).onWakeup(0.9, "ni hao xiao guang");
    }

    /** 连续 ASR 期间再次唤醒，先静默取消旧轮次，防止旧 final 混入新 session。 */
    @Test
    public void onWakeup_duringAsr_cancelsOldAsrBeforeForwarding() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);
        fireAuthSuccess();
        IVoiceService.WakeupListener external = mock(IVoiceService.WakeupListener.class);
        manager.setWakeupListener(external);
        manager.startASR();

        ArgumentCaptor<IWakeupEngine.WakeupListener> captor =
                ArgumentCaptor.forClass(IWakeupEngine.WakeupListener.class);
        verify(wakeupEngine).init(org.mockito.ArgumentMatchers.any(), captor.capture());
        captor.getValue().onWakeup(0.9, "ni hao xiao guang");

        verify(asrEngine).stop();
        verify(external).onWakeup(0.9, "ni hao xiao guang");
    }

    /** 未注册 WakeupListener 时兜底直接 startASR（BR-003），不抛异常。 */
    @Test
    public void onWakeup_noListener_fallsBackToStartAsr() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);
        fireAuthSuccess();
        fireEngineInit(asrEngine, IASREngine.ASRListener.class, 0);
        fireEngineInit(vadEngine, IVadEngine.VadListener.class, 0);
        fireEngineInit(wakeupEngine, IWakeupEngine.WakeupListener.class, 0);
        fireEngineInit(ttsEngine, ITTSEngine.TTSListener.class, 0);

        ArgumentCaptor<IWakeupEngine.WakeupListener> captor =
                ArgumentCaptor.forClass(IWakeupEngine.WakeupListener.class);
        verify(wakeupEngine).init(org.mockito.ArgumentMatchers.any(), captor.capture());
        // 兜底路径：无外部监听器时内部 startASR。
        try {
            captor.getValue().onWakeup(0.8, "ni hao xiao guang");
        } catch (Throwable t) {
            // JVM 单测下 LocalVadEngine.mRecorder (Android AudioRecord) 不可用，忽略录制异常
        }
        verify(asrEngine, times(1)).start(VoiceServiceConstants.ASR_NO_SPEECH_TIMEOUT);
    }

    /** 70904 必须停止 VAD/ASR 并只上报错误，不能遗留占麦会话。 */
    @Test
    public void onAsrTimeout_stopsVadAndAsrThenForwardsError() {
        prepareEngines();
        VoiceServiceManager manager = newManager();
        manager.init(callback);
        fireAuthSuccess();

        ArgumentCaptor<IASREngine.ASRListener> sdkListener =
                ArgumentCaptor.forClass(IASREngine.ASRListener.class);
        verify(asrEngine).init(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), sdkListener.capture());
        sdkListener.getValue().onInit(0);

        IVoiceService.ASRListener external = mock(IVoiceService.ASRListener.class);
        manager.setASRListener(external);
        sdkListener.getValue().onError(VoiceServiceConstants.ASR_TIMEOUT_ERROR_CODE, "no speech");

        verify(vadEngine, org.mockito.Mockito.atLeastOnce()).stop();
        verify(asrEngine, times(1)).stop();
        verify(external, times(1)).onASRError(-1L,
                VoiceServiceConstants.ASR_TIMEOUT_ERROR_CODE, "no speech");
        verify(external, never()).onASRResult(org.mockito.ArgumentMatchers.anyLong(),
                org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.anyBoolean());
    }

    // ---- 辅助 ----

    private void prepareEngines() {
        org.mockito.Mockito.when(speechProvider.getASREngine()).thenReturn(asrEngine);
        org.mockito.Mockito.when(speechProvider.getWakeupEngine()).thenReturn(wakeupEngine);
        org.mockito.Mockito.when(speechProvider.getVadEngine()).thenReturn(vadEngine);
        org.mockito.Mockito.when(speechProvider.getTTSEngine()).thenReturn(ttsEngine);
    }

    private VoiceServiceManager newManager() {
        Context context = mock(Context.class);
        org.mockito.Mockito.when(context.getExternalCacheDir())
                .thenReturn(new File(System.getProperty("java.io.tmpdir")));
        return new VoiceServiceManager(context, speechProvider);
    }

    private void fireAuthSuccess() {
        ArgumentCaptor<ISpeechProvider.AuthCallback> captor =
                ArgumentCaptor.forClass(ISpeechProvider.AuthCallback.class);
        verify(speechProvider).auth(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), captor.capture());
        captor.getValue().onAuthSuccess();
    }

    private void fireAuthError() {
        ArgumentCaptor<ISpeechProvider.AuthCallback> captor =
                ArgumentCaptor.forClass(ISpeechProvider.AuthCallback.class);
        verify(speechProvider).auth(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), captor.capture());
        captor.getValue().onAuthError("auth-fail", "no network");
    }

    /**
     * 捕获引擎 init 注册的监听器并触发 onInit(status)。
     */
    @SuppressWarnings("unchecked")
    private void fireEngineInit(Object engine, Class<?> listenerType, int status) {
        ArgumentCaptor<Object> captor = ArgumentCaptor.forClass((Class<Object>) (Class<?>) listenerType);
        if (engine instanceof IASREngine) {
            verify((IASREngine) engine).init(org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any(), (IASREngine.ASRListener) captor.capture());
            ((IASREngine.ASRListener) captor.getValue()).onInit(status);
        } else if (engine instanceof IVadEngine) {
            verify((IVadEngine) engine).init(org.mockito.ArgumentMatchers.any(),
                    (IVadEngine.VadListener) captor.capture());
            ((IVadEngine.VadListener) captor.getValue()).onInit(status);
        } else if (engine instanceof IWakeupEngine) {
            verify((IWakeupEngine) engine).init(org.mockito.ArgumentMatchers.any(),
                    (IWakeupEngine.WakeupListener) captor.capture());
            ((IWakeupEngine.WakeupListener) captor.getValue()).onInit(status);
        } else if (engine instanceof ITTSEngine) {
            verify((ITTSEngine) engine).init(org.mockito.ArgumentMatchers.any(),
                    org.mockito.ArgumentMatchers.any(), (ITTSEngine.TTSListener) captor.capture());
            ((ITTSEngine.TTSListener) captor.getValue()).onInit(status);
        }
    }
}
