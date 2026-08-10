package com.huawei.aifttr.digitalpersonshell.sdk.impl;

import com.aispeech.AIError;
import com.aispeech.export.config.AILocalVadConfig;
import com.aispeech.export.engines2.AILocalVadEngine;
import com.aispeech.export.listeners.AILocalVadListener;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IVadEngine;

/**
 * 本地 VAD 引擎 DUI 桥接（移植自 Shell）。
 */
public class VadEngineHelper implements IVadEngine {
    private static final String VAD_RESOURCE = "vad_aihome_v0.11.bin";

    private AILocalVadEngine mVadEngine;
    private VadListener listener;

    @Override
    public void init(VadConfigParams configParams, VadListener listener) {
        this.listener = listener;
        mVadEngine = AILocalVadEngine.createInstance();

        AILocalVadConfig.Builder configBuilder = new AILocalVadConfig.Builder()
                .setVadResource(VAD_RESOURCE)
                .setPauseTime(configParams.getPauseTime())
                .setMultiMode(configParams.getMultiMode())
                .setUseFullMode(configParams.isUseFullMode());
        if (configParams.getPauseTimeArray() != null) {
            configBuilder.setPauseTimeArray(configParams.getPauseTimeArray());
        }
        AILocalVadConfig config = configBuilder.build();
        mVadEngine.init(config, new MyLocalVadListener());
    }

    @Override
    public void start() {
        mVadEngine.start();
    }

    @Override
    public void feedData(byte[] buffer, int size) {
        mVadEngine.feedData(buffer, size);
    }

    @Override
    public void stop() {
        mVadEngine.stop();
    }

    @Override
    public void destroy() {
        mVadEngine.destroy();
    }

    private class MyLocalVadListener implements AILocalVadListener {
        @Override
        public void onInit(int status) {
            listener.onInit(status);
        }

        @Override
        public void onError(AIError aiError) {
            listener.onError(aiError.getErrId(), aiError.getError());
        }

        @Override
        public void onVadStart(String recordId) {
            listener.onVadStart(recordId);
        }

        @Override
        public void onBufferReceived(byte[] bytes) {
            listener.onBufferReceived(bytes);
        }

        @Override
        public void onVadEnd(String s) {
        }

        @Override
        public void onRmsChanged(float v) {
        }

        @Override
        public void onResults(String s) {
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
        public void onDestroy(int i) {
        }
    }
}
