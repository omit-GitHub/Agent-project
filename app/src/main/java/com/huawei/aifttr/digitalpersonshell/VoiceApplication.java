package com.huawei.aifttr.digitalpersonshell;

import android.app.Application;
import android.util.Log;

import com.huawei.aifttr.digitalpersonshell.utils.log.LogConfig;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.services.VoiceServiceManager;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.sdk.SpeechProvider;

/**
 * 语音装配入口（真机集成）。
 * <p>
 * 在 Application 启动时构造 {@link SpeechProvider}（DUI 桥接）与
 * {@link VoiceServiceManager}（4 引擎编排），触发授权 + 引擎 init，
 * 并静态暴露 {@link VoiceServiceManager} 供 {@link VoiceForegroundService} 取用。
 * JVM 单测下不创建 Application，{@link #getVoiceService()} 返回 null，不影响注入式测试。
 */
public class VoiceApplication extends Application {

    private static final String TAG = VoiceApplication.class.getSimpleName();

    private static VoiceApplication sInstance;

    private VoiceServiceManager voiceServiceManager;

    @Override
    public void onCreate() {
        super.onCreate();
        sInstance = this;

        // 日志初始化：本地落盘到 cache/log，Logcat debug 版输出
        LogConfig.getInstance()
                .setLogPath(getExternalCacheDir().getAbsolutePath() + "/log")
                .setLogFileName("guiagent");
        Logger.isDebugMode = true;

        Logger.info(TAG, "[VOICE] ====== VoiceApplication 启动，开始装配语音服务 ======");
        SpeechProvider provider = new SpeechProvider();
        provider.init(this);

        voiceServiceManager = new VoiceServiceManager(this, provider);
        voiceServiceManager.init(new IVoiceService.InitCallback() {
            @Override
            public void onSuccess() {
                Logger.info(TAG, "[VOICE] 语音服务初始化成功（4 引擎就绪）");
                Log.i(TAG, "语音服务初始化成功");
            }

            @Override
            public void onError(String errorCode, String errorInfo) {
                Logger.error(TAG, "[VOICE] 语音服务初始化失败 ErrorCode=" + errorCode + " ErrorInfo=" + errorInfo);
                Log.e(TAG, "语音服务初始化失败 ErrorCode=" + errorCode + " ErrorInfo=" + errorInfo);
            }
        });
    }

    /**
     * 取已装配的 {@link VoiceServiceManager}；未装配（JVM 单测）返回 null。
     */
    public static VoiceServiceManager getVoiceService() {
        return sInstance != null ? sInstance.voiceServiceManager : null;
    }
}
