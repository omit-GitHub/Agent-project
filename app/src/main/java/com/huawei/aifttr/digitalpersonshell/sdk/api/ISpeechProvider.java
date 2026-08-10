package com.huawei.aifttr.digitalpersonshell.sdk.api;

import android.content.Context;

/**
 * 三方提供思必驰 SDK 的桥接接口（声纹引擎方法已裁剪，BR-007）。
 * <p>
 * :voice 仅声明此接口；DUI 实现由 :app 的 SpeechProvider + EngineHelper 提供。
 */
public interface ISpeechProvider {
    /** 初始化思必驰模块。 */
    void init(Context context);

    /** 思必驰授权。 */
    void auth(Context context, SdkAuthConfig sdkAuthConfig, AuthCallback authCallback);

    /** 开启日志。 */
    void openLog(Context context, String logPath);

    /** 思必驰内核版本。 */
    String getCoreVersion();

    IASREngine getASREngine();

    IWakeupEngine getWakeupEngine();

    IVadEngine getVadEngine();

    ITTSEngine getTTSEngine();

    /** 授权配置聚合。 */
    class SdkAuthConfig {
        private AuthConfigParams authConfigParams;
        private UploadConfigParams uploadConfigParams;
        private NetConfigParams netConfigParams;
        private EchoConfigParams echoConfigParams;
        private int audioRecorderType;

        public AuthConfigParams getAuthConfigParams() { return authConfigParams; }
        public void setAuthConfigParams(AuthConfigParams authConfigParams) { this.authConfigParams = authConfigParams; }
        public UploadConfigParams getUploadConfigParams() { return uploadConfigParams; }
        public void setUploadConfigParams(UploadConfigParams uploadConfigParams) { this.uploadConfigParams = uploadConfigParams; }
        public NetConfigParams getNetConfigParams() { return netConfigParams; }
        public void setNetConfigParams(NetConfigParams netConfigParams) { this.netConfigParams = netConfigParams; }
        public EchoConfigParams getEchoConfigParams() { return echoConfigParams; }
        public void setEchoConfigParams(EchoConfigParams echoConfigParams) { this.echoConfigParams = echoConfigParams; }
        public int getAudioRecorderType() { return audioRecorderType; }
        public void setAudioRecorderType(int audioRecorderType) { this.audioRecorderType = audioRecorderType; }
    }

    class AuthConfigParams {
        private String deviceName;
        private int authTimeout;
        private boolean loadSerial;
        private boolean loadMacAddress;
        private String offlineProfileName;
        private String deviceProfileDirPath;

        public String getDeviceName() { return deviceName; }
        public void setDeviceName(String deviceName) { this.deviceName = deviceName; }
        public int getAuthTimeout() { return authTimeout; }
        public void setAuthTimeout(int authTimeout) { this.authTimeout = authTimeout; }
        public boolean isLoadSerial() { return loadSerial; }
        public void setLoadSerial(boolean loadSerial) { this.loadSerial = loadSerial; }
        public boolean isLoadMacAddress() { return loadMacAddress; }
        public void setLoadMacAddress(boolean loadMacAddress) { this.loadMacAddress = loadMacAddress; }
        public String getOfflineProfileName() { return offlineProfileName; }
        public void setOfflineProfileName(String offlineProfileName) { this.offlineProfileName = offlineProfileName; }
        public String getDeviceProfileDirPath() { return deviceProfileDirPath; }
        public void setDeviceProfileDirPath(String deviceProfileDirPath) { this.deviceProfileDirPath = deviceProfileDirPath; }
    }

    class UploadConfigParams {
        private boolean uploadEnable;
        public boolean isUploadEnable() { return uploadEnable; }
        public void setUploadEnable(boolean uploadEnable) { this.uploadEnable = uploadEnable; }
    }

    /** 网络配置（OkHttpClient.Builder 以 Object 透传，避免 :voice 引入 okhttp 依赖）。 */
    class NetConfigParams {
        private Object okHttpClientBuilder;
        public Object getOkHttpClientBuilder() { return okHttpClientBuilder; }
        public void setOkHttpClientBuilder(Object okHttpClientBuilder) { this.okHttpClientBuilder = okHttpClientBuilder; }
    }

    class EchoConfigParams {
        private int channels;
        private int micNumber;
        private int exchangeAudioChannel;
        private String savedDirPath;

        public int getChannels() { return channels; }
        public void setChannels(int channels) { this.channels = channels; }
        public int getMicNumber() { return micNumber; }
        public void setMicNumber(int micNumber) { this.micNumber = micNumber; }
        public int getExchangeAudioChannel() { return exchangeAudioChannel; }
        public void setExchangeAudioChannel(int exchangeAudioChannel) { this.exchangeAudioChannel = exchangeAudioChannel; }
        public String getSavedDirPath() { return savedDirPath; }
        public void setSavedDirPath(String savedDirPath) { this.savedDirPath = savedDirPath; }
    }

    /** 授权结果回调。 */
    interface AuthCallback {
        void onAuthSuccess();
        void onAuthError(String errorCode, String errorInfo);
    }
}
