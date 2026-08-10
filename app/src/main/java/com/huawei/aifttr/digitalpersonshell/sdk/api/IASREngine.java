package com.huawei.aifttr.digitalpersonshell.sdk.api;

import org.json.JSONObject;

/**
 * 思必驰语音识别引擎接口。
 */
public interface IASREngine {
    void init(ASRIntentParams intentParams, ASRConfigParams configParams, ASRListener asrListener);

    void start(int timeoutMills);

    void setWakeupEngine(IWakeupEngine wakeupEngine, String wakeupWord);

    /** 切换 SDK 内部 FESPX 音频与应用层自定义 feedData 音频。 */
    void setUseCustomFeed(boolean useCustomFeed);

    void stop();

    void destroy();

    void feedData(byte[] data, int length);

    int getCurrentState();

    class ASRIntentParams {
        private String server;
        private boolean enablePunctuation;
        private String resourceType;
        private boolean cloudVadEnable;
        private boolean realback;
        private boolean useCustomFeed;
        private boolean useOneShot;
        private String[] phrasesList;

        public String getServer() { return server; }
        public void setServer(String server) { this.server = server; }
        public boolean isEnablePunctuation() { return enablePunctuation; }
        public void setEnablePunctuation(boolean enablePunctuation) { this.enablePunctuation = enablePunctuation; }
        public String getResourceType() { return resourceType; }
        public void setResourceType(String resourceType) { this.resourceType = resourceType; }
        public boolean isCloudVadEnable() { return cloudVadEnable; }
        public void setCloudVadEnable(boolean cloudVadEnable) { this.cloudVadEnable = cloudVadEnable; }
        public boolean isRealback() { return realback; }
        public void setRealback(boolean realback) { this.realback = realback; }
        public boolean isUseCustomFeed() { return useCustomFeed; }
        public void setUseCustomFeed(boolean useCustomFeed) { this.useCustomFeed = useCustomFeed; }
        public boolean isUseOneShot() { return useOneShot; }
        public void setUseOneShot(boolean useOneShot) { this.useOneShot = useOneShot; }
        public String[] getPhrasesList() { return phrasesList; }
        public void setPhrasesList(String[] phrasesList) { this.phrasesList = phrasesList; }
    }

    class ASRConfigParams {
        private boolean localVadEnable;
        public boolean isLocalVadEnable() { return localVadEnable; }
        public void setLocalVadEnable(boolean localVadEnable) { this.localVadEnable = localVadEnable; }
    }

    interface ASRListener {
        void onInit(int status);
        void onError(int errorCode, String errorDes);
        void onResults(JSONObject resultObject);
        void onBeginningOfSpeech();
    }
}
