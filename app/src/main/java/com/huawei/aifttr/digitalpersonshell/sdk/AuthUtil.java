package com.huawei.aifttr.digitalpersonshell.sdk;

import android.annotation.SuppressLint;
import android.content.Context;
import android.provider.Settings;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ISpeechProvider;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;

import java.io.File;

import okhttp3.OkHttpClient;

/**
 * 授权装配（移植自 Shell 的 voiceservices.auth.AuthUtil）。
 * <p>
 * 构造思必驰在线授权所需的 {@link ISpeechProvider.SdkAuthConfig}：
 * customDeviceName 取 android_id（DUI 在线授权必填），并配齐 timeout/profile/upload/net/
 * audioRecorderType。{@link com.huawei.aifttr.digitalpersonshell.sdk.SpeechProvider} 仅在 authParams 非空时
 * 才设置 AuthConfig，故调用方必须经此处装配，不可传裸 SdkAuthConfig。
 * SDK 的 init 已由 {@link com.huawei.aifttr.digitalpersonshell.VoiceApplication} 前置完成，此处不重复。
 */
public final class AuthUtil {
    private static final String TAG = AuthUtil.class.getSimpleName();

    private AuthUtil() {
    }

    @SuppressLint("HardwareIds")
    private static String getAndroidId(Context context) {
        return Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
    }

    /**
     * 授权：构造 SdkAuthConfig 并触发思必驰在线授权。
     *
     * @param context 上下文
     * @param speechProvider 思必驰桥接
     * @param callback 授权结果回调
     */
    public static void auth(Context context, ISpeechProvider speechProvider,
                            ISpeechProvider.AuthCallback callback) {
        Logger.info(TAG, "[VOICE] 授权装配开始，构造 SdkAuthConfig");
        ISpeechProvider.SdkAuthConfig sdkAuthConfig = new ISpeechProvider.SdkAuthConfig();

        String androidId = getAndroidId(context);

        ISpeechProvider.AuthConfigParams authConfigParams = new ISpeechProvider.AuthConfigParams();
        authConfigParams.setDeviceName(androidId);
        authConfigParams.setAuthTimeout(5000);
        authConfigParams.setLoadSerial(false);
        authConfigParams.setLoadMacAddress(true);
        authConfigParams.setOfflineProfileName(androidId);
        File profilePath = context.getExternalFilesDir("profile/");
        if (profilePath != null) {
            authConfigParams.setDeviceProfileDirPath(profilePath.toString());
        }
        sdkAuthConfig.setAuthConfigParams(authConfigParams);

        ISpeechProvider.UploadConfigParams uploadConfigParams = new ISpeechProvider.UploadConfigParams();
        uploadConfigParams.setUploadEnable(false);
        sdkAuthConfig.setUploadConfigParams(uploadConfigParams);

        ISpeechProvider.NetConfigParams netConfigParams = new ISpeechProvider.NetConfigParams();
        netConfigParams.setOkHttpClientBuilder(new OkHttpClient.Builder());
        sdkAuthConfig.setNetConfigParams(netConfigParams);

        sdkAuthConfig.setAudioRecorderType(VoiceServiceConstants.TYPE_COMMON_LINE4);

        Logger.info(TAG, "[VOICE] 授权装配完成 deviceName=" + androidId
                + " recorderType=" + VoiceServiceConstants.TYPE_COMMON_LINE4
                + " coreVersion=" + speechProvider.getCoreVersion());
        speechProvider.auth(context, sdkAuthConfig, callback);
    }
}
