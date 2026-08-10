package com.huawei.aifttr.digitalpersonshell.sdk.api;

/**
 * 思必驰语音活动检测引擎接口。
 */
public interface IVadEngine {
    void init(VadConfigParams configParams, VadListener listener);

    void start();

    void feedData(byte[] buffer, int size);

    void stop();

    void destroy();

    class VadConfigParams {
        private int pauseTime;
        private int[] pauseTimeArray;
        private int multiMode;
        private boolean useFullMode;

        public int getPauseTime() { return pauseTime; }
        public void setPauseTime(int pauseTime) { this.pauseTime = pauseTime; }
        public int[] getPauseTimeArray() { return pauseTimeArray; }
        public void setPauseTimeArray(int[] pauseTimeArray) { this.pauseTimeArray = pauseTimeArray; }
        public int getMultiMode() { return multiMode; }
        public void setMultiMode(int multiMode) { this.multiMode = multiMode; }
        public boolean isUseFullMode() { return useFullMode; }
        public void setUseFullMode(boolean useFullMode) { this.useFullMode = useFullMode; }
    }

    interface VadListener {
        void onInit(int status);
        void onError(int errorCode, String errorDes);
        void onVadStart(String recordId);
        void onBufferReceived(byte[] bytes);
    }
}
