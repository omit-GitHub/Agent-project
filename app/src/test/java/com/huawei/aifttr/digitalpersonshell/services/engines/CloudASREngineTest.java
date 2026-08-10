package com.huawei.aifttr.digitalpersonshell.services.engines;

import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IASREngine;

import org.json.JSONObject;
import org.junit.Test;
import org.mockito.ArgumentCaptor;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public class CloudASREngineTest {

    @Test
    public void finalWithoutRec_reusesLatestPartialText() throws Exception {
        IASREngine engine = mock(IASREngine.class);
        CloudASREngine.ASRCallBack callback = mock(CloudASREngine.ASRCallBack.class);
        new CloudASREngine(false, callback, engine);

        ArgumentCaptor<IASREngine.ASRListener> listenerCaptor =
                ArgumentCaptor.forClass(IASREngine.ASRListener.class);
        verify(engine).init(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), listenerCaptor.capture());

        JSONObject partial = mock(JSONObject.class);
        JSONObject partialResult = mock(JSONObject.class);
        when(partial.getInt("eof")).thenReturn(0);
        when(partial.getJSONObject("result")).thenReturn(partialResult);
        when(partialResult.getString("var")).thenReturn("这是下一轮");

        JSONObject finished = mock(JSONObject.class);
        JSONObject finishedResult = mock(JSONObject.class);
        when(finished.getInt("eof")).thenReturn(VoiceServiceConstants.ASR_END_FLAG);
        when(finished.getJSONObject("result")).thenReturn(finishedResult);
        when(finishedResult.getString("rec")).thenReturn("");

        listenerCaptor.getValue().onResults(partial);
        listenerCaptor.getValue().onResults(finished);

        verify(callback).onASRResult("这是下一轮", false);
        verify(callback).onASRResult("这是下一轮", true);
    }

    @Test
    public void startCustomFeed_switchesAudioSourceBeforeStart() {
        IASREngine engine = mock(IASREngine.class);
        CloudASREngine.ASRCallBack callback = mock(CloudASREngine.ASRCallBack.class);
        CloudASREngine cloud = new CloudASREngine(false, callback, engine);

        cloud.startASREngine(true);

        verify(engine).setUseCustomFeed(true);
        verify(engine).start(VoiceServiceConstants.ASR_NO_SPEECH_TIMEOUT);
    }

    @Test
    public void normalStart_usesWakeupFespxInsteadOfCustomFeed() {
        IASREngine engine = mock(IASREngine.class);
        CloudASREngine cloud = new CloudASREngine(false,
                mock(CloudASREngine.ASRCallBack.class), engine);

        cloud.startASREngine();

        verify(engine).setUseCustomFeed(false);
        verify(engine).start(VoiceServiceConstants.ASR_NO_SPEECH_TIMEOUT);
    }
}
