package com.huawei.aifttr.digitalpersonshell.sdk.impl;

import com.aispeech.AIError;
import com.aispeech.AIResult;
import com.aispeech.export.config.AICloudASRConfig;
import com.aispeech.export.engines2.AICloudASREngine;
import com.aispeech.export.engines2.AILocalSignalAndWakeupEngine;
import com.aispeech.export.intent.AICloudASRIntent;
import com.aispeech.export.listeners.AIASRListener;
import com.aispeech.lite.BaseProcessor;
import com.aispeech.lite.speech.Phrase;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IASREngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;

import org.json.JSONObject;

/**
 * 云端 ASR 引擎 DUI 桥接（移植自 Shell）。
 */
public class ASREngineHelper implements IASREngine {
    private static final String TAG = ASREngineHelper.class.getSimpleName();
    private static final String VAD_RESOURCE = "vad_aihome_v0.11.bin";

    private AICloudASREngine mCloudASREngine;
    private final AICloudASRIntent mASRIntent = new AICloudASRIntent();
    private ASRListener asrListener;

    @Override
    public void init(ASRIntentParams intentParams, ASRConfigParams configParams, ASRListener asrListener) {
        this.asrListener = asrListener;
        if (intentParams.getServer() != null) {
            mASRIntent.setServer(intentParams.getServer());
        }
        mASRIntent.setEnablePunctuation(intentParams.isEnablePunctuation());
        if (intentParams.getResourceType() != null) {
            mASRIntent.setResourceType(intentParams.getResourceType());
        }
        mASRIntent.setCloudVadEnable(intentParams.isCloudVadEnable());
        mASRIntent.setRealback(intentParams.isRealback());
        mASRIntent.setUseCustomFeed(intentParams.isUseCustomFeed());
        mASRIntent.setUseOneShot(intentParams.isUseOneShot());
        if (intentParams.getPhrasesList() != null) {
            Phrase networkProtectionPhrase = new Phrase(intentParams.getPhrasesList());
            mASRIntent.setPhrasesList(new Phrase[]{networkProtectionPhrase});
        }

        AICloudASRConfig config = new AICloudASRConfig();
        config.setVadResource(VAD_RESOURCE);
        config.setLocalVadEnable(configParams.isLocalVadEnable());
        mCloudASREngine = AICloudASREngine.createInstance();
        Logger.info(TAG, "[VOICE] DUI ASR init: vadRes=" + VAD_RESOURCE
                + " localVad=" + configParams.isLocalVadEnable()
                + " oneShot=" + intentParams.isUseOneShot()
                + " customFeed=" + intentParams.isUseCustomFeed()
                + " server=" + intentParams.getServer());
        mCloudASREngine.init(config, new MyASRListener());
    }

    @Override
    public void start(int timeoutMills) {
        WakeupEngineHelper wakeupHelper = WakeupEngineHelper.getInstance();
        if (wakeupHelper != null) {
            AILocalSignalAndWakeupEngine fespxEngine = wakeupHelper.getLocalSignalAndWakeupEngine();
            if (fespxEngine != null) {
                mASRIntent.setFespxEngine(fespxEngine);
                Logger.info(TAG, "[VOICE] ASR start: 绑定 fespx(one-shot 共享唤醒引擎音频) timeout=" + timeoutMills);
            } else {
                Logger.warn(TAG, "[VOICE] ASR start: fespxEngine 为 null，one-shot 音频来源异常 timeout=" + timeoutMills);
            }
        } else {
            Logger.warn(TAG, "[VOICE] ASR start: WakeupEngineHelper 单例为 null timeout=" + timeoutMills);
        }
        mASRIntent.setNoSpeechTimeOut(timeoutMills);
        mCloudASREngine.start(mASRIntent);
    }

    @Override
    public void setWakeupEngine(IWakeupEngine wakeupEngine, String wakeupWord) {
        if (wakeupEngine instanceof WakeupEngineHelper) {
            mASRIntent.setFespxEngine(((WakeupEngineHelper) wakeupEngine).getLocalSignalAndWakeupEngine());
            mASRIntent.setWakeupWord(wakeupWord);
        }
    }

    @Override
    public void setUseCustomFeed(boolean useCustomFeed) {
        mASRIntent.setUseCustomFeed(useCustomFeed);
    }

    @Override
    public void stop() {
        mCloudASREngine.cancel();
    }

    @Override
    public void destroy() {
        mCloudASREngine.destroy();
    }

    @Override
    public void feedData(byte[] data, int length) {
        mCloudASREngine.feedData(data, length);
    }

    @Override
    public int getCurrentState() {
        BaseProcessor.EngineState state = mCloudASREngine.getCurrentState();
        return state.getValue();
    }

    private class MyASRListener implements AIASRListener {
        @Override
        public void onInit(int status) {
            Logger.info(TAG, "[VOICE] DUI CloudASR onInit status=" + status);
            asrListener.onInit(status);
        }

        @Override
        public void onError(AIError aiError) {
            Logger.error(TAG, "[VOICE] DUI CloudASR onError errId=" + aiError.getErrId()
                    + " err=" + aiError.getError());
            asrListener.onError(aiError.getErrId(), aiError.getError());
        }

        @Override
        public void onResults(AIResult aiResult) {
            JSONObject resultObject = aiResult.getResultJSONObject();
            asrListener.onResults(resultObject);
        }

        @Override
        public void onRmsChanged(float v) {
        }

        @Override
        public void onBeginningOfSpeech() {
            asrListener.onBeginningOfSpeech();
        }

        @Override
        public void onEndOfSpeech() {
        }

        @Override
        public void onReadyForSpeech() {
        }

        @Override
        public void onResultDataReceived(byte[] bytes, int i, int i1) {
        }

        @Override
        public void onRawDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onResultDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onNotOneShot() {
        }
    }
}
