package com.huawei.aifttr.digitalpersonshell.services.engines;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;

import java.io.File;

/**
 * 本地唤醒引擎包装（移植自源库，去声纹裁剪音频透传，BR-008）。
 */
public class LocalWakeupEngine {
    private static final String TAG = LocalWakeupEngine.class.getSimpleName();

    private IWakeupEngine wakeupEngine;
    private WakeupCallBack callback;
    private boolean isInit = false;
    private File fileRoot;

    public LocalWakeupEngine(File fileRoot, WakeupCallBack callback, IWakeupEngine wakeupEngine) {
        if ((fileRoot == null) || (callback == null) || (wakeupEngine == null)) {
            Logger.error(TAG, "[VOICE] 构造参数为 null: fileRoot=" + fileRoot
                    + " callback=" + (callback == null) + " engine=" + (wakeupEngine == null));
            return;
        }
        this.fileRoot = fileRoot;
        this.callback = callback;
        this.wakeupEngine = wakeupEngine;
        IWakeupEngine.WakeupConfigParams configParams = new IWakeupEngine.WakeupConfigParams();
        configParams.setWakeupWords(new String[]{VoiceServiceConstants.ASR_WAKEUP_WORD});
        configParams.setMajors(new int[]{1});
        configParams.setThresholds(new float[]{0.26f});
        configParams.setCustomNet(new String[]{"0", "1"});
        configParams.setEnableNet(new String[]{"1", "1"});
        configParams.setThreshHigh(new float[]{0.38f, 0.48f});
        configParams.setThreshLow(new float[]{0.9f, 0.85f});
        configParams.setEchoChannelNum(2);
        Logger.info(TAG, "[VOICE] 唤醒引擎 init: wakeupWord=" + VoiceServiceConstants.ASR_WAKEUP_WORD
                + " threshold=0.26 echoChannelNum=2");
        wakeupEngine.init(configParams, new MyWakeupListener());
    }

    public IWakeupEngine getWakeupEngine() {
        return wakeupEngine;
    }

    public void setWakeupWord(String wakeupWordStr) {
        wakeupEngine.setWakeupWord(wakeupWordStr, 0.1f, 1);
    }

    public void start() {
        try {
            IWakeupEngine.WakeupIntentParams intentParams = new IWakeupEngine.WakeupIntentParams();
            File speechDir = new File(fileRoot, "speech");
            String speechCanonicalPath = speechDir.getCanonicalPath();
            String fileRootCanonicalPath = fileRoot.getCanonicalPath() + File.separator;
            if (!speechDir.getAbsolutePath().equals(speechCanonicalPath)
                    || !speechCanonicalPath.startsWith(fileRootCanonicalPath)) {
                Logger.error(TAG, "[VOICE] speech dir symlink or path escape detected");
                return;
            }
            intentParams.setSaveAudioPath(speechCanonicalPath);
            Logger.info(TAG, "[VOICE] 唤醒引擎 start: saveAudioPath=" + speechCanonicalPath);
            wakeupEngine.start(intentParams);
        } catch (Exception e) {
            Logger.error(TAG, "[VOICE] start wakeup fail, ", e);
        }
    }

    public void stop() {
        Logger.info(TAG, "[VOICE] 唤醒引擎 stop");
        wakeupEngine.stop();
    }

    public void destroy() {
        Logger.info(TAG, "[VOICE] 唤醒引擎 destroy");
        wakeupEngine.destroy();
    }

    private class MyWakeupListener implements IWakeupEngine.WakeupListener {
        @Override
        public void onInit(int status) {
            isInit = true;
            if (status == VoiceServiceConstants.OPT_SUCCESS) {
                Logger.info(TAG, "[VOICE] DUI 唤醒 onInit status=0(成功)");
                callback.onInit();
            } else {
                Logger.error(TAG, "[VOICE] DUI 唤醒 onInit 失败 status=" + status);
                callback.onInitError(status, "init wakeup fail!");
            }
        }

        @Override
        public void onError(int errorCode, String errorDes) {
            Logger.error(TAG, "[VOICE] DUI 唤醒 onError errCode=" + errorCode + " des=" + errorDes);
            if (!isInit) {
                isInit = true;
                callback.onInitError(errorCode, errorDes);
            } else {
                stop();
            }
        }

        @Override
        public void onWakeup(double confidence, String wakeupWord) {
            Logger.info(TAG, "[VOICE] ★唤醒命中★ confidence=" + confidence + " wakeupWord=" + wakeupWord);
            callback.onWakeup(confidence, wakeupWord);
        }
    }

    /**
     * 唤醒回调（声纹数据回调已删除，BR-008）。
     */
    public interface WakeupCallBack {
        void onInit();
        void onInitError(int errorCode, String errorDes);
        void onWakeup(double confidence, String wakeupWord);
    }
}
