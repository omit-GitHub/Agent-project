package com.huawei.aifttr.digitalpersonshell.services.engines;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IASREngine;
import com.huawei.aifttr.digitalpersonshell.sdk.api.IWakeupEngine;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;

/**
 * 云端语音识别引擎包装（移植自源库，audio 仅调试用 BR-009）。
 */
public class CloudASREngine {
    private static final String TAG = CloudASREngine.class.getSimpleName();

    private ASRCallBack callback;
    private IASREngine asrEngine;
    private final ByteArrayOutputStream cachePcm =
            new ByteArrayOutputStream(VoiceServiceConstants.INIT_ASR_CACHE_LEN);
    private ByteArrayOutputStream voiceData;
    private boolean isInit = false;
    private final StringBuilder totalWords = new StringBuilder();
    private String latestWords = "";

    public CloudASREngine(boolean setUseCustomFeed, ASRCallBack asrCallBack, IASREngine asrEngine) {
        if (asrCallBack == null || asrEngine == null) {
            Logger.error(TAG, "[VOICE] ASR 构造参数为 null");
            return;
        }
        this.callback = asrCallBack;
        this.asrEngine = asrEngine;
        voiceData = new ByteArrayOutputStream();

        IASREngine.ASRIntentParams intentParams = new IASREngine.ASRIntentParams();
        intentParams.setServer(VoiceServiceConstants.ASR_SERVER_URL);
        intentParams.setEnablePunctuation(false);
        intentParams.setResourceType(VoiceServiceConstants.ASR_RESOURCE_TYPE);
        intentParams.setCloudVadEnable(true);
        intentParams.setRealback(true);
        intentParams.setUseCustomFeed(setUseCustomFeed);
        intentParams.setUseOneShot(true);
        intentParams.setPhrasesList(new String[]{"访客WIFI", "幻彩灯带", "小明手机", "网络保障"});

        IASREngine.ASRConfigParams configParams = new IASREngine.ASRConfigParams();
        configParams.setLocalVadEnable(true);

        Logger.info(TAG, "[VOICE] ASR init: server=" + VoiceServiceConstants.ASR_SERVER_URL
                + " resourceType=aihome useCustomFeed=" + setUseCustomFeed
                + " oneShot=true cloudVad=true localVad=true");
        asrEngine.init(intentParams, configParams, new MyASRListener());
    }

    public byte[] getVoiceData() {
        return voiceData.toByteArray();
    }

    public void setWakeupEngine(IWakeupEngine wakeupEngine, String wakeupWord) {
        asrEngine.setWakeupEngine(wakeupEngine, wakeupWord);
    }

    public void startASREngine() {
        startASREngine(false);
    }

    public void startASREngine(boolean useCustomFeed) {
        Logger.info(TAG, "[VOICE] ASR 引擎 start, noSpeechTimeout="
                + VoiceServiceConstants.ASR_NO_SPEECH_TIMEOUT + " customFeed=" + useCustomFeed);
        totalWords.setLength(0);
        latestWords = "";
        cachePcm.reset();
        voiceData.reset();
        asrEngine.setUseCustomFeed(useCustomFeed);
        asrEngine.start(VoiceServiceConstants.ASR_NO_SPEECH_TIMEOUT);
    }

    public void destroyASR() {
        Logger.info(TAG, "[VOICE] ASR destroyASR");
        totalWords.setLength(0);
        asrEngine.destroy();
    }

    public void stopASREngine() {
        Logger.info(TAG, "[VOICE] ASR stopASREngine, cachePcm.size=" + cachePcm.size());
        cachePcm.reset();
        totalWords.setLength(0);
        voiceData.reset();
        asrEngine.stop();
    }

    public void feedData(byte[] bytes) {
        int state = asrEngine.getCurrentState();
        if (state != VoiceServiceConstants.ASR_STATE_RUNNING) {
            writeToCache(bytes);
            return;
        }
        byte[] totalData = retrieveData(bytes);
        asrEngine.feedData(totalData, totalData.length);
        try {
            voiceData.write(bytes);
        } catch (IOException e) {
            Logger.error(TAG, "[VOICE] write error", e);
        }
    }

    private void writeToCache(byte[] data) {
        if (cachePcm.size() > VoiceServiceConstants.MAX_ASR_CACHE_LEN) {
            return;
        }
        try {
            cachePcm.write(data);
        } catch (IOException e) {
            Logger.error(TAG, "writeToCache: error write cache", e);
        }
    }

    private byte[] retrieveData(byte[] rest) {
        try {
            cachePcm.write(rest);
        } catch (IOException e) {
            cachePcm.reset();
            return rest;
        }
        byte[] total = cachePcm.toByteArray();
        cachePcm.reset();
        return total;
    }

    private class MyASRListener implements IASREngine.ASRListener {
        @Override
        public void onInit(int status) {
            isInit = true;
            if (status == VoiceServiceConstants.OPT_SUCCESS) {
                Logger.info(TAG, "[VOICE] DUI ASR onInit status=0(成功)");
                callback.onInit();
            } else {
                Logger.error(TAG, "[VOICE] DUI ASR onInit 失败 status=" + status);
                callback.onInitError(status, "init asr fail!");
            }
        }

        @Override
        public void onError(int errorCode, String errorDes) {
            if (!isInit) {
                isInit = true;
                Logger.error(TAG, "[VOICE] DUI ASR init 阶段 onError errCode=" + errorCode + " des=" + errorDes);
                callback.onInitError(errorCode, errorDes);
            } else {
                Logger.error(TAG, "[VOICE] DUI ASR 运行期 onError errCode=" + errorCode + " des=" + errorDes);
                callback.onASRResultError(errorCode, errorDes);
            }
        }

        @Override
        public void onResults(JSONObject resultObject) {
            try {
                boolean isFinish = resultObject.getInt("eof") == VoiceServiceConstants.ASR_END_FLAG;
                JSONObject obj = resultObject.getJSONObject("result");
                String words = obj.getString(isFinish ? "rec" : "var");
                String curWords = totalWords + words;
                if (isFinish) {
                    if (words == null || words.trim().isEmpty()) {
                        curWords = latestWords;
                    } else {
                        totalWords.append(words);
                        curWords = totalWords.toString();
                    }
                } else if (curWords != null && !curWords.trim().isEmpty()) {
                    latestWords = curWords;
                }
                Logger.info(TAG, "[VOICE] ASR onResults isFinish=" + isFinish + " words=" + words
                        + " total=" + totalWords);
                callback.onASRResult(curWords, isFinish);
            } catch (JSONException e) {
                Logger.error(TAG, "[VOICE] ASR JSON 解析失败", e);
                callback.onASRResultError(VoiceServiceConstants.ASR_JSON_ERROR, e.getMessage());
            }
        }

        @Override
        public void onBeginningOfSpeech() {
            callback.onSpeechStart();
        }
    }

    public interface ASRCallBack {
        void onInit();
        void onInitError(int errorCode, String errorDes);
        void onASRResult(String words, boolean isFinish);
        void onASRResultError(int errorCode, String errorDes);
        void onSpeechStart();
    }
}
