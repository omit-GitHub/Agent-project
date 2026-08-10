package com.huawei.aifttr.digitalpersonshell.sdk.impl;

import com.aispeech.AIError;
import com.aispeech.DUILiteConfig;
import com.aispeech.DUILiteSDK;
import com.aispeech.export.config.AILocalSignalAndWakeupConfig;
import com.aispeech.export.engines2.AILocalSignalAndWakeupEngine;
import com.aispeech.export.intent.AILocalSignalAndWakeupIntent;
import com.aispeech.export.listeners.AILocalSignalAndWakeupListener;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceConfig;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;

/**
 * 本地唤醒引擎 DUI 桥接（移植自 Shell，去声纹）。
 * <p>
 * 声纹裁剪音频透传已删除（BR-008）；{@link #buildWakeupConfig()} 产出
 * {@link WakeupConfigSpec}，其 implVprintCutCk 固定为 false，
 * 应用到 DUI config 时 {@code setImplVprintCutCk(false)}。
 */
public class WakeupEngineHelper implements IWakeupEngine {
    private static final String TAG = WakeupEngineHelper.class.getSimpleName();

    private static final String SSPE_DUAL_REF0_RES =
            "sspe_aec-ula-bss-wkp_36mm_ch4-2mic-1null-1ref_outgain14_v2.0.0.165_20260209_1.bin";
    private static final String SSPE_LINE4_REF0_RES =
            "sspe_aec_ula_bss_wkp_40mm_ch6_4mic_2ref_v2.0.0.175_vpon.bin";
    private static final String SSPE_CIRCLE4_REF0_RES =
            "sspe_uca-wkp_70mm_ch4_4mic_0ref_release-v2.0.0.140.bin";
    private static final String SSPE_CIRCLE6_REF0_RES =
            "sspe_uca-wkp_72mm_ch6_6mic_0ref_release-v2.0.0.140.bin";

    private static volatile WakeupEngineHelper sInstance;

    private AILocalSignalAndWakeupEngine mLocalSignalAndWakeupEngine;
    private WakeupListener listener;

    public WakeupEngineHelper() {
        mLocalSignalAndWakeupEngine = AILocalSignalAndWakeupEngine.createInstance();
        sInstance = this;
    }

    /**
     * 构建唤醒配置规格（纯 Java，不触 DUI，可单测）。
     * implVprintCutCk 固定 false（BR-008）。
     */
    public static WakeupConfigSpec buildWakeupConfig() {
        return new WakeupConfigSpec(
                VoiceConfig.WAKEUP_RES,
                SSPE_DUAL_REF0_RES,
                new String[]{"ni hao xiao guang"},
                new int[]{1},
                new float[]{0.26f},
                false);
    }

    /**
     * 按录音类型选取 beamforming 资源（运行期触 DUI）。
     */
    private static String pickSspeResource() {
        switch (DUILiteSDK.getAudioRecorderType()) {
            case DUILiteConfig.TYPE_COMMON_DUAL:
                return SSPE_DUAL_REF0_RES;
            case DUILiteConfig.TYPE_COMMON_LINE4:
                return SSPE_LINE4_REF0_RES;
            case DUILiteConfig.TYPE_COMMON_CIRCLE4:
                return SSPE_CIRCLE4_REF0_RES;
            case DUILiteConfig.TYPE_COMMON_CIRCLE6:
                return SSPE_CIRCLE6_REF0_RES;
            default:
                return SSPE_DUAL_REF0_RES;
        }
    }

    public static WakeupEngineHelper getInstance() {
        return sInstance;
    }

    public AILocalSignalAndWakeupEngine getLocalSignalAndWakeupEngine() {
        return mLocalSignalAndWakeupEngine;
    }

    @Override
    public void init(WakeupConfigParams params, WakeupListener listener) {
        this.listener = listener;
        WakeupConfigSpec spec = buildWakeupConfig();
        String sspeRes = pickSspeResource();
        int recorderType = DUILiteSDK.getAudioRecorderType();
        Logger.info(TAG, "[VOICE] 唤醒 DUI init: wakeupRes=" + spec.getWakeupResource()
                + " sspeRes=" + sspeRes + " recorderType=" + recorderType
                + " wakeupWords=" + java.util.Arrays.toString(spec.getWakeupWords())
                + " implVprintCutCk=" + spec.isImplVprintCutCk());
        AILocalSignalAndWakeupConfig config = new AILocalSignalAndWakeupConfig();
        config.setSspeResource(sspeRes);
        config.setWakeupResource(spec.getWakeupResource());
        if (params.getWakeupWords() != null && params.getMajors() != null) {
            config.setWakeupWord(params.getWakeupWords(), params.getMajors());
        }
        if (params.getThresholds() != null) {
            config.setThreshold(params.getThresholds());
        }
        // BR-008：不向声纹透传裁剪音频
        config.setImplVprintCutCk(spec.isImplVprintCutCk());
        mLocalSignalAndWakeupEngine.init(config, new MyLocalSignalAndWakeupListenerImpl());
    }

    @Override
    public void start(WakeupIntentParams intentParams) {
        Logger.info(TAG, "[VOICE] 唤醒 DUI start: recorderType=" + DUILiteSDK.getAudioRecorderType());
        AILocalSignalAndWakeupIntent intent = new AILocalSignalAndWakeupIntent();
        mLocalSignalAndWakeupEngine.start(intent);
    }

    @Override
    public void stop() {
        Logger.info(TAG, "[VOICE] 唤醒 DUI stop");
        mLocalSignalAndWakeupEngine.stop();
    }

    @Override
    public void setWakeupWord(String wakeupWordStr, float threshold, int major) {
        com.aispeech.export.config.WakeupWord wakeupWord =
                new com.aispeech.export.config.WakeupWord(wakeupWordStr, threshold, major);
        mLocalSignalAndWakeupEngine.setWakeupword(wakeupWord);
    }

    @Override
    public void destroy() {
        mLocalSignalAndWakeupEngine.destroy();
        sInstance = null;
    }

    private class MyLocalSignalAndWakeupListenerImpl implements AILocalSignalAndWakeupListener {
        @Override
        public void onInit(int status) {
            Logger.info(TAG, "[VOICE] 唤醒 DUI onInit status=" + status);
            listener.onInit(status);
        }

        @Override
        public void onError(AIError aiError) {
            Logger.error(TAG, "[VOICE] 唤醒 DUI onError errId=" + aiError.getErrId()
                    + " err=" + aiError.getError());
            listener.onError(aiError.getErrId(), aiError.getError());
        }

        @Override
        public void onWakeup(double confidence, String wakeupWord) {
            Logger.info(TAG, "[VOICE] 唤醒 DUI onWakeup confidence=" + confidence
                    + " word=" + wakeupWord);
            listener.onWakeup(confidence, wakeupWord);
        }

        @Override
        public void onWakeup(String wakeupWord) {
        }

        @Override
        public void onNearInformation(String s) {
        }

        @Override
        public void onDoaResult(int doa) {
        }

        @Override
        public void onReadyForSpeech() {
        }

        @Override
        public void onRawDataReceived(byte[] bytes, int size) {
        }

        @Override
        public void onResultDataReceived(byte[] bytes, int size, int wakeupType) {
        }

        /**
         * DUI SDK 强制回调：裁剪音频。空实现——不向声纹透传（声纹已裁剪，BR-008）。
         */
        @Override
        public void onVprintCutDataReceived(int dataType, byte[] bytes, int size) {
        }

        @Override
        public void onAgcDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onInputDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onOutputDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onEchoDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onSevcDoaResult(int i) {
        }

        @Override
        public void onSevcNoiseResult(String s) {
        }

        @Override
        public void onMultibfDataReceived(byte[] bytes, int i, int i1) {
        }

        @Override
        public void onEchoVoipDataReceived(byte[] bytes, int i) {
        }

        @Override
        public void onVadDataReceived(byte[] bytes, int i) {
        }
    }
}
