package com.huawei.aifttr.digitalpersonshell.sdk;

import android.content.Context;

import com.aispeech.AIEchoConfig;
import com.aispeech.DUILiteConfig;
import com.aispeech.DUILiteSDK;
import com.aispeech.export.config.AINetConfig;
import com.aispeech.export.config.AuthConfig;
import com.aispeech.export.config.UploadConfig;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceConfig;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IASREngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ISpeechProvider;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ITTSEngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IVadEngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.ASREngineHelper;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.TTSEngineHelper;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.VadEngineHelper;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.WakeupEngineHelper;

/**
 * DUI SDK 桥接（移植自 Shell，声纹引擎方法已裁剪，BR-007）。
 * 授权凭证沿用 Shell（VoiceConfig）。
 */
public class SpeechProvider implements ISpeechProvider {
    private static final String TAG = SpeechProvider.class.getSimpleName();

    private static final String ECHO_RES = VoiceConfig.SSPE_RES;

    private WakeupEngineHelper wakeupEngineHelper;

    @Override
    public void init(Context context) {
        Logger.info(TAG, "[VOICE] DUILiteSDK.init 开始");
        DUILiteSDK.init(context);
        Logger.info(TAG, "[VOICE] DUILiteSDK.init 完成 coreVersion=" + DUILiteSDK.getCoreVersion());
    }

    @Override
    public void auth(Context context, SdkAuthConfig sdkAuthConfig, AuthCallback authCallback) {
        Logger.info(TAG, "[VOICE] 授权开始: audioRecorderType=" + sdkAuthConfig.getAudioRecorderType()
                + " echoConfig=" + (sdkAuthConfig.getEchoConfigParams() != null));
        DUILiteConfig.Builder duiConfigBuilder = new DUILiteConfig.Builder();

        AuthConfigParams authParams = sdkAuthConfig.getAuthConfigParams();
        if (authParams != null) {
            AuthConfig authConfig = getAuthConfig(authParams);
            authConfig.setAuthServer(VoiceConfig.AUTH_SERVER_URL);
            duiConfigBuilder.setAuthConfig(authConfig);
        }

        UploadConfigParams uploadParams = sdkAuthConfig.getUploadConfigParams();
        if (uploadParams != null) {
            UploadConfig uploadConfig = getUploadConfig(uploadParams);
            duiConfigBuilder.setUploadConfig(uploadConfig);
        }

        NetConfigParams netParams = sdkAuthConfig.getNetConfigParams();
        if (netParams != null) {
            AINetConfig netConfig = getNetConfig(netParams);
            duiConfigBuilder.setNetConfig(netConfig);
        }

        EchoConfigParams echoParams = sdkAuthConfig.getEchoConfigParams();
        if (echoParams != null) {
            AIEchoConfig aiEchoConfig = getEchoConfig(echoParams);
            duiConfigBuilder.setEchoConfig(aiEchoConfig);
        }

        DUILiteConfig config = duiConfigBuilder.setApiKey(VoiceConfig.AUTH_API_KEY)
                .setProductId(VoiceConfig.AUTH_PRODUCT_ID)
                .setProductKey(VoiceConfig.AUTH_PRODUCT_KEY)
                .setProductSecret(VoiceConfig.AUTH_PRODUCT_SECRET)
                .create();

        config.setAudioRecorderType(sdkAuthConfig.getAudioRecorderType());

        DUILiteSDK.doAuth(context, config, new DUILiteSDK.InitListener() {
            @Override
            public void success() {
                Logger.info(TAG, "[VOICE] 授权成功, recorderType=" + config.getAudioRecorderType()
                        + " coreVersion=" + DUILiteSDK.getCoreVersion());
                if (authCallback != null) {
                    authCallback.onAuthSuccess();
                }
            }

            @Override
            public void error(final String errorCode, final String errorInfo) {
                Logger.error(TAG, "[VOICE] 授权失败 errCode=" + errorCode + " info=" + errorInfo);
                if (authCallback != null) {
                    authCallback.onAuthError(errorCode, errorInfo);
                }
            }
        });
    }

    @Override
    public void openLog(Context context, String logPath) {
        DUILiteSDK.openLog(context, logPath);
    }

    @Override
    public String getCoreVersion() {
        return DUILiteSDK.getCoreVersion();
    }

    @Override
    public IASREngine getASREngine() {
        return new ASREngineHelper();
    }

    @Override
    public IWakeupEngine getWakeupEngine() {
        if (wakeupEngineHelper == null) {
            wakeupEngineHelper = new WakeupEngineHelper();
        }
        return wakeupEngineHelper;
    }

    @Override
    public IVadEngine getVadEngine() {
        return new VadEngineHelper();
    }

    @Override
    public ITTSEngine getTTSEngine() {
        return new TTSEngineHelper();
    }

    AuthConfig getAuthConfig(AuthConfigParams authParams) {
        AuthConfig.Builder authConfigBuilder = new AuthConfig.Builder();
        if (authParams.getDeviceName() != null) {
            authConfigBuilder.setCustomDeviceName(authParams.getDeviceName());
        }
        if (authParams.getOfflineProfileName() != null) {
            authConfigBuilder.setOfflineProfileName(authParams.getOfflineProfileName());
        }
        if (authParams.getDeviceProfileDirPath() != null) {
            authConfigBuilder.setDeviceProfileDirPath(authParams.getDeviceProfileDirPath());
        }
        return authConfigBuilder.setAuthTimeout(authParams.getAuthTimeout())
                .setLoadSerial(authParams.isLoadSerial())
                .setLoadMacAddress(authParams.isLoadMacAddress())
                .create();
    }

    UploadConfig getUploadConfig(UploadConfigParams uploadParams) {
        return new UploadConfig.Builder()
                .setUploadEnable(uploadParams.isUploadEnable())
                .create();
    }

    AINetConfig getNetConfig(NetConfigParams netConfigParams) {
        AINetConfig.Builder netConfigBuilder = new AINetConfig.Builder();
        if (netConfigParams.getOkHttpClientBuilder() != null) {
            netConfigBuilder.customOkHttpClientBuilder(
                    (okhttp3.OkHttpClient.Builder) netConfigParams.getOkHttpClientBuilder());
        }
        return netConfigBuilder.build();
    }

    AIEchoConfig getEchoConfig(EchoConfigParams echoConfigParams) {
        AIEchoConfig aiEchoConfig = new AIEchoConfig();
        aiEchoConfig.setAecResource(ECHO_RES);
        aiEchoConfig.setChannels(echoConfigParams.getChannels());
        aiEchoConfig.setMicNumber(echoConfigParams.getMicNumber());
        aiEchoConfig.setExchangeAudioChannel(echoConfigParams.getExchangeAudioChannel());
        return aiEchoConfig;
    }
}
