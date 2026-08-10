package com.huawei.aifttr.digitalpersonshell.services.engines;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IVadEngine;
import com.huawei.aifttr.digitalpersonshell.recorder.Recorder;
import com.huawei.aifttr.digitalpersonshell.recorder.RecorderListener;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;

import java.util.ArrayDeque;

/**
 * 本地语音活动检测引擎包装（移植自源库）。
 */
public class LocalVadEngine {
    private static final String TAG = LocalVadEngine.class.getSimpleName();

    private IVadEngine vadEngine;
    private Recorder bargeInRecorder;
    private Recorder activeRecorder;
    private RecorderListener recorderListener;
    private VadCallBack callback;
    private boolean isInit = false;
    private volatile boolean bargeInMode = false;
    private volatile boolean bargeSpeechStarted = false;
    private final Object rawBufferLock = new Object();
    private final ArrayDeque<byte[]> rawBargeInBuffer = new ArrayDeque<>();
    private int rawBargeInBytes = 0;
    private static final int MAX_RAW_BARGE_IN_BYTES = 32_000; // 1s, 16kHz PCM16 mono

    public LocalVadEngine(VadCallBack callback, IVadEngine vadEngine) {
        if (callback == null || vadEngine == null) {
            Logger.error(TAG, "param has null");
            return;
        }
        this.callback = callback;
        this.vadEngine = vadEngine;
        initVadEngine();
        initRecorderListener();
    }

    private void initRecorderListener() {
        recorderListener = new RecorderListener() {
            @Override
            public void onRecordStarted() {
                Logger.info(TAG, "[VOICE] 拾音器 onRecordStarted，启动 VAD");
                if (vadEngine != null) {
                    vadEngine.start();
                }
            }

            @Override
            public void onDataReceived(byte[] buffer, int size) {
                boolean forwardRaw = bargeInMode && bargeSpeechStarted;
                if (bargeInMode && !bargeSpeechStarted) {
                    synchronized (rawBufferLock) {
                        rawBargeInBuffer.addLast(buffer);
                        rawBargeInBytes += size;
                        while (rawBargeInBytes > MAX_RAW_BARGE_IN_BYTES
                                && !rawBargeInBuffer.isEmpty()) {
                            rawBargeInBytes -= rawBargeInBuffer.removeFirst().length;
                        }
                    }
                }
                if (vadEngine != null) {
                    vadEngine.feedData(buffer, size);
                }
                // 命中后直接透传 VOICE_COMMUNICATION 的 AEC 原始流，
                // 不再等待 VAD onBufferReceived，避免再次裁掉语音开头。
                if (forwardRaw) {
                    callback.feedData(buffer);
                }
            }

            @Override
            public void onRecordStopped() {
                Logger.info(TAG, "[VOICE] 拾音器 onRecordStopped");
            }

            @Override
            public void onRecordReleased() {
            }

            @Override
            public void onException(Exception e) {
                Logger.error(TAG, "[VOICE] 拾音器异常:", e);
            }
        };
    }

    private void initVadEngine() {
        IVadEngine.VadConfigParams configParams = new IVadEngine.VadConfigParams();
        configParams.setPauseTime(2000);
        configParams.setPauseTimeArray(new int[]{300, 500, 2000});
        configParams.setMultiMode(1);
        configParams.setUseFullMode(true);
        Logger.info(TAG, "[VOICE] VAD init: pauseTime=2000 multiMode=1 useFullMode=true");
        vadEngine.init(configParams, new MyVadListener());
    }

    /** 使用系统 VOICE_COMMUNICATION(AEC/NS) 音源启动插话检测。 */
    public boolean startBargeIn() {
        if (bargeInRecorder == null) {
            bargeInRecorder = new Recorder();
            if (!bargeInRecorder.createVoiceCommunication()) {
                Logger.warn(TAG, "[VOICE] VOICE_COMMUNICATION 录音源初始化失败，禁用普通语音打断");
                bargeInRecorder.release();
                bargeInRecorder = null;
                return false;
            }
        }
        Logger.info(TAG, "[VOICE] LocalVadEngine.startBargeIn: VOICE_COMMUNICATION + VAD");
        resetBargeInState(true);
        activeRecorder = bargeInRecorder;
        activeRecorder.start(recorderListener);
        if (!activeRecorder.isRecording()) {
            Logger.warn(TAG, "[VOICE] VOICE_COMMUNICATION 拾音启动失败，禁用普通语音打断");
            activeRecorder = null;
            vadEngine.stop();
            return false;
        }
        return true;
    }

    public void stop() {
        Logger.info(TAG, "[VOICE] LocalVadEngine.stop");
        vadEngine.stop();
        Recorder recorder = activeRecorder;
        activeRecorder = null;
        if (recorder != null) {
            recorder.stop();
        }
        resetBargeInState(false);
    }

    public void destroy() {
        if (bargeInRecorder != null) {
            bargeInRecorder.release();
            bargeInRecorder = null;
        }
        if (vadEngine != null) {
            vadEngine.destroy();
        }
    }

    private class MyVadListener implements IVadEngine.VadListener {
        @Override
        public void onInit(int status) {
            isInit = true;
            if (status == VoiceServiceConstants.OPT_SUCCESS) {
                Logger.info(TAG, "[VOICE] DUI VAD onInit status=0(成功)");
                callback.onInit();
            } else {
                Logger.error(TAG, "[VOICE] DUI VAD onInit 失败 status=" + status);
                callback.onInitError(status, "");
            }
        }

        @Override
        public void onVadStart(String recordId) {
            Logger.info(TAG, "[VOICE] VAD 检测到语音起点 recordId=" + recordId);
            byte[] preRoll = new byte[0];
            if (bargeInMode) {
                synchronized (rawBufferLock) {
                    preRoll = new byte[rawBargeInBytes];
                    int offset = 0;
                    for (byte[] bytes : rawBargeInBuffer) {
                        System.arraycopy(bytes, 0, preRoll, offset, bytes.length);
                        offset += bytes.length;
                    }
                    rawBargeInBuffer.clear();
                    rawBargeInBytes = 0;
                    bargeSpeechStarted = true;
                }
            }
            callback.onSpeechStart(preRoll);
        }

        @Override
        public void onBufferReceived(byte[] bytes) {
            if (!bargeInMode) {
                callback.feedData(bytes);
            }
        }

        @Override
        public void onError(int errorCode, String errorDes) {
            Logger.error(TAG, "[VOICE] VAD onError errCode=" + errorCode + " des=" + errorDes);
            if (!isInit) {
                isInit = true;
                callback.onInitError(errorCode, errorDes);
            } else {
                stop();
            }
        }
    }

    public interface VadCallBack {
        void onInit();
        void onInitError(int errorCode, String errorDes);
        void onSpeechStart(byte[] preRoll);
        void feedData(byte[] bytes);
    }

    private void resetBargeInState(boolean enabled) {
        synchronized (rawBufferLock) {
            bargeInMode = enabled;
            bargeSpeechStarted = false;
            rawBargeInBuffer.clear();
            rawBargeInBytes = 0;
        }
    }
}
