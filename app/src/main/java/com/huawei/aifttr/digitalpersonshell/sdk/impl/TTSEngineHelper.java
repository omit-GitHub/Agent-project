package com.huawei.aifttr.digitalpersonshell.sdk.impl;

import com.aispeech.AIError;
import com.aispeech.export.config.AICloudTTSConfig;
import com.aispeech.export.engines2.AICloudTTSEngine;
import com.aispeech.export.intent.AICloudTTSIntent;
import com.aispeech.export.listeners.AITTSListener;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ITTSEngine;

import org.json.JSONArray;

/**
 * 云端 TTS 引擎 DUI 桥接（移植自 Shell）。
 */
public class TTSEngineHelper implements ITTSEngine {
    private AICloudTTSEngine mCloudTTSEngine;
    private final AICloudTTSIntent mTTSIntent = new AICloudTTSIntent();
    private TTSListener listener;

    @Override
    public void init(TTSIntentParams intentParams, TTSConfigParams configParams, TTSListener listener) {
        this.listener = listener;
        if (intentParams.getTextType() != null) {
            mTTSIntent.setTextType(intentParams.getTextType());
        }
        if (intentParams.getSpeakingStyle() != null) {
            mTTSIntent.setSpeakingStyle(intentParams.getSpeakingStyle());
        }
        mTTSIntent.setReturnPhone(intentParams.isReturnPhone());
        mTTSIntent.setHighLightInfo(intentParams.isHighLightInfo());
        if (intentParams.getAudioType() != null) {
            mTTSIntent.setAudioType(intentParams.getAudioType());
        }
        if (intentParams.getSpeaker() != null) {
            mTTSIntent.setSpeaker(intentParams.getSpeaker());
        }
        if (intentParams.getTtsServer() != null) {
            mTTSIntent.setServer(intentParams.getTtsServer());
        }
        mCloudTTSEngine = AICloudTTSEngine.createInstance();
        AICloudTTSConfig config = new AICloudTTSConfig();
        config.setUseCache(configParams.isUseCache());
        mCloudTTSEngine.init(config, new MyTTSListener());
    }

    @Override
    public void start(String words, String id, float speed) {
        mTTSIntent.setSpeed(speed);
        mCloudTTSEngine.speak(mTTSIntent, words, id);
    }

    @Override
    public void setSpeaker(String speaker) {
        mTTSIntent.setSpeaker(speaker);
    }

    @Override
    public void stop() {
        mCloudTTSEngine.stop();
    }

    @Override
    public void destroy() {
        mCloudTTSEngine.destroy();
    }

    private class MyTTSListener implements AITTSListener {
        @Override
        public void onInit(int status) {
            listener.onInit(status);
        }

        @Override
        public void onError(String id, AIError aiError) {
            listener.onError(id, aiError.getErrId(), aiError.getError());
        }

        @Override
        public void onReady(String id) {
        }

        @Override
        public void onCompletion(String id) {
            listener.onCompletion(id);
        }

        @Override
        public void onProgress(int currentTime, int totalTime, boolean isRefTextTTSFinished) {
            listener.onProgress(currentTime, totalTime, isRefTextTTSFinished);
        }

        @Override
        public void onSynthesizeStart(String s) {
        }

        @Override
        public void onSynthesizeDataArrived(String s, byte[] bytes) {
        }

        @Override
        public void onSynthesizeFinish(String s) {
        }

        @Override
        public void onTimestampReceived(byte[] bytes, int i) {
        }

        @Override
        public void onPhonemesDataArrived(String s, String s1) {
        }

        @Override
        public void onHighInfoReceived(JSONArray jsonArray, int i, int i1, int i2) {
        }
    }
}
