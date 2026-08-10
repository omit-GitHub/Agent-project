package com.huawei.aifttr.digitalpersonshell.sdk.api;

/**
 * 思必驰语音唤醒引擎接口（声纹裁剪音频回调已删除，BR-008）。
 */
public interface IWakeupEngine {
    void init(WakeupConfigParams configParams, WakeupListener callBack);

    void start(WakeupIntentParams intentParams);

    void stop();

    void setWakeupWord(String wakeupWordStr, float threshold, int major);

    void destroy();

    class WakeupConfigParams {
        private String[] wakeupWords;
        private int[] majors;
        private float[] thresholds;
        private String[] customNet;
        private String[] enableNet;
        private float[] threshHigh;
        private float[] threshLow;
        private int echoChannelNum;

        public String[] getWakeupWords() { return wakeupWords; }
        public void setWakeupWords(String[] wakeupWords) { this.wakeupWords = wakeupWords; }
        public int[] getMajors() { return majors; }
        public void setMajors(int[] majors) { this.majors = majors; }
        public float[] getThresholds() { return thresholds; }
        public void setThresholds(float[] thresholds) { this.thresholds = thresholds; }
        public String[] getCustomNet() { return customNet; }
        public void setCustomNet(String[] customNet) { this.customNet = customNet; }
        public String[] getEnableNet() { return enableNet; }
        public void setEnableNet(String[] enableNet) { this.enableNet = enableNet; }
        public float[] getThreshHigh() { return threshHigh; }
        public void setThreshHigh(float[] threshHigh) { this.threshHigh = threshHigh; }
        public float[] getThreshLow() { return threshLow; }
        public void setThreshLow(float[] threshLow) { this.threshLow = threshLow; }
        public int getEchoChannelNum() { return echoChannelNum; }
        public void setEchoChannelNum(int echoChannelNum) { this.echoChannelNum = echoChannelNum; }
    }

    class WakeupIntentParams {
        private String saveAudioPath;
        public String getSaveAudioPath() { return saveAudioPath; }
        public void setSaveAudioPath(String saveAudioPath) { this.saveAudioPath = saveAudioPath; }
    }

    /**
     * 唤醒回调（声纹裁剪音频回调已删除，BR-008）。
     */
    interface WakeupListener {
        void onInit(int status);

        void onError(int errorCode, String errorDes);

        void onWakeup(double confidence, String wakeupWord);
    }
}
