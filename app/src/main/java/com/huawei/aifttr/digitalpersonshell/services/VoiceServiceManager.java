package com.huawei.aifttr.digitalpersonshell.services;

import android.content.Context;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ISpeechProvider;
import com.huawei.aifttr.digitalpersonshell.sdk.AuthUtil;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;
import com.huawei.aifttr.digitalpersonshell.services.engines.CloudASREngine;
import com.huawei.aifttr.digitalpersonshell.services.engines.CloudTTSEngine;
import com.huawei.aifttr.digitalpersonshell.services.engines.LocalVadEngine;
import com.huawei.aifttr.digitalpersonshell.services.engines.LocalWakeupEngine;

import java.io.File;
import java.util.ArrayDeque;

/**
 * 语音 SDK 编排层（4 引擎：ASR/VAD/Wakeup/TTS，声纹已裁剪）。
 * <p>
 * 实现 {@link IVoiceService}：init 先授权，授权成功后构造 4 引擎包装，
 * 全部 init 成功才回调 onSuccess；任一失败回调 onError（BR-001/002）。
 *
 * @see IVoiceService
 */
public class VoiceServiceManager implements IVoiceService {
    private static final String TAG = VoiceServiceManager.class.getSimpleName();

    private final Context context;
    private final ISpeechProvider speechProvider;

    private CloudASREngine cloudASREngine;
    private LocalVadEngine localVadEngine;
    private LocalWakeupEngine localWakeupEngine;
    private CloudTTSEngine cloudTTSEngine;

    private final boolean[] isEngineInit = new boolean[VoiceServiceConstants.ENGINE_INIT_NUM];
    private int engineInitCount = 0;
    private int wakeupInitCount = 0;

    private final boolean isASRWakeupWord = true;
    private long asrGeneration = 0L;
    private long activeAsrId = -1L;

    private enum CaptureMode {
        IDLE,
        FESPX_ASR,
        BARGE_DETECT,
        BARGE_ASR_FLUSH,
        BARGE_ASR
    }

    private final Object captureLock = new Object();
    private CaptureMode captureMode = CaptureMode.IDLE;
    private final ArrayDeque<byte[]> bargeInAudioBuffer = new ArrayDeque<>();
    private int bargeInBufferedBytes = 0;
    private static final int MAX_BARGE_IN_BUFFER_BYTES = 16_000; // 500ms, 16kHz PCM16 mono

    private IVoiceService.InitCallback initCallback;
    private IVoiceService.ASRListener asrListener;
    private IVoiceService.TTSListener ttsListener;
    private IVoiceService.WakeupListener wakeupListener;
    private IVoiceService.BargeInListener bargeInListener;

    private final CloudASREngine.ASRCallBack asrCallBack = new CloudASREngine.ASRCallBack() {
        @Override
        public void onInit() {
            isEngineInit[VoiceServiceConstants.ASR_ENGINE_INDEX] = true;
            Logger.info(TAG, "[VOICE] ASR 引擎 init 成功");
            checkAllEngineInit();
            if (isASRWakeupWord) {
                startWakeupEngine();
            }
        }

        @Override
        public void onInitError(int errorCode, String errorDes) {
            isEngineInit[VoiceServiceConstants.ASR_ENGINE_INDEX] = false;
            Logger.error(TAG, "[VOICE] ASR 引擎 init 失败 errCode=" + errorCode + " des=" + errorDes);
            checkAllEngineInit();
            if (isASRWakeupWord) {
                startWakeupEngine();
            }
        }

        @Override
        public void onASRResult(String words, boolean isFinish) {
            Logger.info(TAG, "[VOICE] ASR 结果 words=" + words + " isFinish=" + isFinish);
            byte[] audio = cloudASREngine.getVoiceData();
            long resultAsrId;
            synchronized (captureLock) {
                resultAsrId = activeAsrId;
            }
            if (isFinish) {
                // 先释放本轮拾音，再通知 Gateway 启动 WS/TTS；避免 Agent 首包过快时
                // 插话 VAD 因旧 ASR 尚未收尾而启动失败。
                localVadEngine.stop();
                synchronized (captureLock) {
                    captureMode = CaptureMode.IDLE;
                    activeAsrId = -1L;
                    clearBargeInBufferLocked();
                }
            }
            if (asrListener != null) {
                asrListener.onASRResult(resultAsrId, words, audio, isFinish);
            }
        }

        @Override
        public void onASRResultError(int errorCode, String errorDes) {
            Logger.error(TAG, "[VOICE] ASR 识别错误 errCode=" + errorCode + " des=" + errorDes);
            long failedAsrId;
            synchronized (captureLock) {
                failedAsrId = activeAsrId;
            }
            stopASRWithoutFinalResult();
            if (asrListener != null) {
                asrListener.onASRError(failedAsrId, errorCode, errorDes);
            }
        }

        @Override
        public void onSpeechStart() {
            long speechAsrId;
            synchronized (captureLock) {
                speechAsrId = activeAsrId;
            }
            if (asrListener != null) {
                asrListener.onASRSpeechStart(speechAsrId);
            }
        }
    };

    private final LocalVadEngine.VadCallBack vadCallBack = new LocalVadEngine.VadCallBack() {
        @Override
        public void onInit() {
            isEngineInit[VoiceServiceConstants.VAD_ENGINE_INDEX] = true;
            Logger.info(TAG, "[VOICE] VAD 引擎 init 成功");
            checkAllEngineInit();
        }

        @Override
        public void onInitError(int errorCode, String errorDes) {
            isEngineInit[VoiceServiceConstants.VAD_ENGINE_INDEX] = false;
            Logger.error(TAG, "[VOICE] VAD 引擎 init 失败 errCode=" + errorCode + " des=" + errorDes);
            checkAllEngineInit();
        }

        @Override
        public void onSpeechStart(byte[] preRoll) {
            BargeInListener listener;
            long bargeAsrId;
            synchronized (captureLock) {
                if (captureMode != CaptureMode.BARGE_DETECT) {
                    return;
                }
                // 不停止 VAD/Recorder：后续语音数据继续从同一 AEC 音频流进入 ASR。
                captureMode = CaptureMode.BARGE_ASR_FLUSH;
                bargeAsrId = ++asrGeneration;
                activeAsrId = bargeAsrId;
                listener = bargeInListener;
                clearBargeInBufferLocked();
            }
            Logger.info(TAG, "[VOICE] 插话 VAD 命中：保持录音流并切换到 ASR");
            if (listener != null) {
                listener.onBargeIn(bargeAsrId);
            }
            cloudASREngine.startASREngine(true);
            if (preRoll != null && preRoll.length > 0) {
                cloudASREngine.feedData(preRoll);
            }
            while (true) {
                ArrayDeque<byte[]> pending;
                synchronized (captureLock) {
                    if (bargeInAudioBuffer.isEmpty()) {
                        captureMode = CaptureMode.BARGE_ASR;
                        break;
                    }
                    pending = new ArrayDeque<>(bargeInAudioBuffer);
                    clearBargeInBufferLocked();
                }
                while (!pending.isEmpty()) {
                    cloudASREngine.feedData(pending.removeFirst());
                }
            }
        }

        @Override
        public void feedData(byte[] bytes) {
            synchronized (captureLock) {
                if (captureMode == CaptureMode.BARGE_DETECT
                        || captureMode == CaptureMode.BARGE_ASR_FLUSH) {
                    bargeInAudioBuffer.addLast(bytes);
                    bargeInBufferedBytes += bytes.length;
                    while (bargeInBufferedBytes > MAX_BARGE_IN_BUFFER_BYTES
                            && !bargeInAudioBuffer.isEmpty()) {
                        bargeInBufferedBytes -= bargeInAudioBuffer.removeFirst().length;
                    }
                    return;
                }
                if (captureMode != CaptureMode.BARGE_ASR) {
                    return;
                }
            }
            cloudASREngine.feedData(bytes);
        }
    };

    private final LocalWakeupEngine.WakeupCallBack wakeupCallBack =
            new LocalWakeupEngine.WakeupCallBack() {
                @Override
                public void onInit() {
                    isEngineInit[VoiceServiceConstants.WAKEUP_ENGINE_INDEX] = true;
                    Logger.info(TAG, "[VOICE] Wakeup 引擎 init 成功");
                    checkAllEngineInit();
                    if (isASRWakeupWord) {
                        startWakeupEngine();
                    }
                }

                @Override
                public void onInitError(int errorCode, String errorDes) {
                    isEngineInit[VoiceServiceConstants.WAKEUP_ENGINE_INDEX] = false;
                    Logger.error(TAG, "[VOICE] Wakeup 引擎 init 失败 errCode=" + errorCode + " des=" + errorDes);
                    checkAllEngineInit();
                    if (isASRWakeupWord) {
                        startWakeupEngine();
                    }
                }

                @Override
                public void onWakeup(double confidence, String wakeupWord) {
                    Logger.info(TAG, "[VOICE] 唤醒命中 wakeupWord=" + wakeupWord
                            + " confidence=" + confidence + "，转发到 WakeupListener 编排");
                    boolean cancelRunningAsr;
                    synchronized (captureLock) {
                        cancelRunningAsr = captureMode == CaptureMode.FESPX_ASR
                                || captureMode == CaptureMode.BARGE_ASR_FLUSH
                                || captureMode == CaptureMode.BARGE_ASR;
                    }
                    if (cancelRunningAsr) {
                        Logger.info(TAG, "[VOICE] 显式唤醒命中，先静默取消上一个 ASR 轮次");
                        stopASRWithoutFinalResult();
                    }
                    // 转发到外部监听器（VoiceGateway）做问候播报 + ASR 联动编排；
                    // 未注册时兜底直接 startASR（BR-003）。
                    if (wakeupListener != null) {
                        wakeupListener.onWakeup(confidence, wakeupWord);
                    } else {
                        startASR();
                    }
                }
            };

    private final CloudTTSEngine.TTSInitCallback ttsInitCallback =
            new CloudTTSEngine.TTSInitCallback() {
                @Override
                public void onInit() {
                    isEngineInit[VoiceServiceConstants.TTS_ENGINE_INDEX] = true;
                    Logger.info(TAG, "[VOICE] TTS 引擎 init 成功");
                    checkAllEngineInit();
                }

                @Override
                public void onInitError(int errorCode, String errorDes) {
                    isEngineInit[VoiceServiceConstants.TTS_ENGINE_INDEX] = false;
                    Logger.error(TAG, "[VOICE] TTS 引擎 init 失败 errCode=" + errorCode + " des=" + errorDes);
                    checkAllEngineInit();
                }
            };

    public VoiceServiceManager(Context context, ISpeechProvider speechProvider) {
        this.context = context;
        this.speechProvider = speechProvider;
    }

    @Override
    public void init(InitCallback callback) {
        this.initCallback = callback;
        Logger.info(TAG, "[VOICE] 语音服务 init 开始，先授权");
        AuthUtil.auth(context, speechProvider, new ISpeechProvider.AuthCallback() {
            @Override
            public void onAuthSuccess() {
                Logger.info(TAG, "[VOICE] 授权成功，开始构造 4 引擎");
                initEngines();
            }

            @Override
            public void onAuthError(String errorCode, String errorInfo) {
                Logger.error(TAG, "[VOICE] 授权失败 errCode=" + errorCode + " info=" + errorInfo);
                if (initCallback != null) {
                    initCallback.onError(errorCode, errorInfo);
                }
            }
        });
    }

    private void initEngines() {
        File fileRoot = context.getExternalCacheDir();
        Logger.info(TAG, "[VOICE] initEngines: fileRoot=" + fileRoot);
        cloudASREngine = new CloudASREngine(false, asrCallBack, speechProvider.getASREngine());
        localVadEngine = new LocalVadEngine(vadCallBack, speechProvider.getVadEngine());
        localWakeupEngine = new LocalWakeupEngine(fileRoot, wakeupCallBack, speechProvider.getWakeupEngine());
        // one-shot ASR 与唤醒 FESPX 共享音频，并由 SDK 裁掉“你好小光”。
        cloudASREngine.setWakeupEngine(localWakeupEngine.getWakeupEngine(),
                VoiceServiceConstants.ASR_WAKEUP_WORD);
        cloudTTSEngine = new CloudTTSEngine(ttsInitCallback, speechProvider.getTTSEngine());
        // 修复时序：setTTSListener 可能在 initEngines 之前（授权异步未完成、cloudTTSEngine 尚未构造）调用，
        // 那时只存 this.ttsListener，CloudTTSEngine.listener 仍为 null，会导致 onCompletion 回调丢失、
        // 流式排队第二段无法推进。构造后补设已注册的 listener。
        if (ttsListener != null) {
            cloudTTSEngine.setTTSListener(ttsListener);
        }
    }

    @Override
    public void setWakeupListener(WakeupListener listener) {
        // 唤醒命中后转发到该监听器（VoiceGateway）编排问候播报 + ASR 联动（BR-003）。
        this.wakeupListener = listener;
    }

    @Override
    public void setASRListener(ASRListener listener) {
        this.asrListener = listener;
    }

    @Override
    public void setTTSListener(TTSListener listener) {
        this.ttsListener = listener;
        if (cloudTTSEngine != null) {
            cloudTTSEngine.setTTSListener(listener);
        }
    }

    @Override
    public void setBargeInListener(BargeInListener listener) {
        this.bargeInListener = listener;
    }

    @Override
    public void setWakeupWord(String wakeupWord) {
        if (localWakeupEngine != null) {
            localWakeupEngine.setWakeupWord(wakeupWord);
        }
    }

    @Override
    public long startASR() {
        Logger.info(TAG, "[VOICE] startASR: 启动云端 ASR 引擎");
        long asrId;
        synchronized (captureLock) {
            captureMode = CaptureMode.FESPX_ASR;
            asrId = ++asrGeneration;
            activeAsrId = asrId;
            clearBargeInBufferLocked();
        }
        cloudASREngine.startASREngine(false);
        return asrId;
    }

    @Override
    public void stopASR() {
        Logger.info(TAG, "[VOICE] stopASR: 停止 VAD + ASR");
        synchronized (captureLock) {
            captureMode = CaptureMode.IDLE;
            activeAsrId = -1L;
            clearBargeInBufferLocked();
        }
        localVadEngine.stop();
        cloudASREngine.stopASREngine();
    }

    @Override
    public boolean startBargeInDetection() {
        synchronized (captureLock) {
            if (captureMode != CaptureMode.IDLE) {
                Logger.warn(TAG, "[VOICE] 插话监听未启动：当前拾音模式=" + captureMode);
                return false;
            }
            captureMode = CaptureMode.BARGE_DETECT;
            clearBargeInBufferLocked();
        }
        boolean started = localVadEngine.startBargeIn();
        if (!started) {
            synchronized (captureLock) {
                if (captureMode == CaptureMode.BARGE_DETECT) {
                    captureMode = CaptureMode.IDLE;
                }
            }
        }
        return started;
    }

    @Override
    public void stopBargeInDetection() {
        synchronized (captureLock) {
            if (captureMode != CaptureMode.BARGE_DETECT) {
                return;
            }
            captureMode = CaptureMode.IDLE;
            clearBargeInBufferLocked();
        }
        localVadEngine.stop();
    }

    private void clearBargeInBufferLocked() {
        bargeInAudioBuffer.clear();
        bargeInBufferedBytes = 0;
    }

    /** 静默取消 ASR；取消永远不合成 final。 */
    private void stopASRWithoutFinalResult() {
        stopASR();
    }

    @Override
    public void startTTS(String text, String id, float speed) {
        cloudTTSEngine.speakInSpeed(text, id, speed);
    }

    @Override
    public void cancelTTS() {
        cloudTTSEngine.stopSpeaking();
    }

    @Override
    public void destroy() {
        synchronized (captureLock) {
            captureMode = CaptureMode.IDLE;
            activeAsrId = -1L;
            clearBargeInBufferLocked();
        }
        if (localVadEngine != null) {
            localVadEngine.stop();
            localVadEngine.destroy();
        }
        if (cloudASREngine != null) {
            cloudASREngine.stopASREngine();
            cloudASREngine.destroyASR();
        }
        if (localWakeupEngine != null) {
            localWakeupEngine.stop();
            localWakeupEngine.destroy();
        }
        if (cloudTTSEngine != null) {
            cloudTTSEngine.stopSpeaking();
            cloudTTSEngine.destroyTTS();
        }
    }

    /**
     * 已 init 成功的引擎数（测试可观测）。
     */
    public int getEngineInitCount() {
        int count = 0;
        for (boolean b : isEngineInit) {
            if (b) {
                count++;
            }
        }
        return count;
    }

    private void startWakeupEngine() {
        wakeupInitCount++;
        Logger.info(TAG, "[VOICE] startWakeupEngine: count=" + wakeupInitCount
                + " asrInit=" + isEngineInit[VoiceServiceConstants.ASR_ENGINE_INDEX]
                + " wakeupInit=" + isEngineInit[VoiceServiceConstants.WAKEUP_ENGINE_INDEX]);
        if (wakeupInitCount == 2) {
            if (isEngineInit[VoiceServiceConstants.ASR_ENGINE_INDEX]
                    && isEngineInit[VoiceServiceConstants.WAKEUP_ENGINE_INDEX]) {
                Logger.info(TAG, "[VOICE] ASR+Wakeup 均 init 成功，启动唤醒监听（你好小光）");
                localWakeupEngine.start();
            } else {
                Logger.warn(TAG, "[VOICE] ASR 或 Wakeup 未 init 成功，唤醒未启动（链路将无法唤醒）");
            }
            wakeupInitCount = 0;
        }
    }

    private void checkAllEngineInit() {
        engineInitCount++;
        if (engineInitCount == VoiceServiceConstants.ENGINE_INIT_NUM) {
            StringBuilder failEngine = new StringBuilder();
            for (int i = 0; i < VoiceServiceConstants.ENGINE_INIT_NUM; i++) {
                if (!isEngineInit[i]) {
                    failEngine.append(VoiceServiceConstants.indexToEngine.get(i));
                }
            }
            if (failEngine.length() == 0) {
                Logger.info(TAG, "[VOICE] 全部 4 引擎 init 成功");
                if (initCallback != null) {
                    initCallback.onSuccess();
                }
            } else {
                failEngine.append("failed!");
                Logger.error(TAG, "[VOICE] 部分引擎 init 失败: " + failEngine);
                if (initCallback != null) {
                    initCallback.onError(
                            VoiceServiceConstants.INIT_ENGINE_ERROR_CODE,
                            failEngine.toString());
                }
            }
            engineInitCount = 0;
        }
    }
}
