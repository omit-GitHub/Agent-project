package com.huawei.aifttr.digitalpersonshell.sdk.api;

/**
 * 思必驰语音播报引擎接口。
 */
public interface ITTSEngine {
    void init(TTSIntentParams intentParams, TTSConfigParams configParams, TTSListener listener);

    void start(String words, String id, float speed);

    void setSpeaker(String speaker);

    void stop();

    void destroy();

    class TTSIntentParams {
        private String textType;
        private String speakingStyle;
        private boolean returnPhone;
        private boolean highLightInfo;
        private String audioType;
        private String speaker;
        private String ttsServer;

        public String getTextType() { return textType; }
        public void setTextType(String textType) { this.textType = textType; }
        public String getSpeakingStyle() { return speakingStyle; }
        public void setSpeakingStyle(String speakingStyle) { this.speakingStyle = speakingStyle; }
        public boolean isReturnPhone() { return returnPhone; }
        public void setReturnPhone(boolean returnPhone) { this.returnPhone = returnPhone; }
        public boolean isHighLightInfo() { return highLightInfo; }
        public void setHighLightInfo(boolean highLightInfo) { this.highLightInfo = highLightInfo; }
        public String getAudioType() { return audioType; }
        public void setAudioType(String audioType) { this.audioType = audioType; }
        public String getSpeaker() { return speaker; }
        public void setSpeaker(String speaker) { this.speaker = speaker; }
        public String getTtsServer() { return ttsServer; }
        public void setTtsServer(String ttsServer) { this.ttsServer = ttsServer; }
    }

    class TTSConfigParams {
        private boolean useCache;
        public boolean isUseCache() { return useCache; }
        public void setUseCache(boolean useCache) { this.useCache = useCache; }
    }

    interface TTSListener {
        void onInit(int status);
        void onError(String id, int errorCode, String errorDes);
        void onCompletion(String id);
        void onProgress(int currentTime, int totalTime, boolean isRefTextTTSFinished);
    }
}
