package com.huawei.aifttr.digitalpersonshell.services.engines;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;
import com.huawei.aifttr.digitalpersonshell.sdk.api.ITTSEngine;
import com.huawei.aifttr.digitalpersonshell.data.model.enums.SpeakerType;
import com.huawei.aifttr.digitalpersonshell.constants.VoiceServiceConstants;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 云端文本转语音引擎包装（移植自源库）。
 */
public class CloudTTSEngine {
    private static final String TAG = CloudTTSEngine.class.getSimpleName();

    private static final Pattern DATETIME_PATTERN = Pattern
            .compile("(\\d{4})-(\\d{1,2})-(\\d{1,2})\\s+(\\d{1,2}):(\\d{2})");
    private static final Map<String, String> CHINESE_DIGIT_MAP = new HashMap<>();

    static {
        CHINESE_DIGIT_MAP.put("0", "零");
        CHINESE_DIGIT_MAP.put("1", "一");
        CHINESE_DIGIT_MAP.put("2", "二");
        CHINESE_DIGIT_MAP.put("3", "三");
        CHINESE_DIGIT_MAP.put("4", "四");
        CHINESE_DIGIT_MAP.put("5", "五");
        CHINESE_DIGIT_MAP.put("6", "六");
        CHINESE_DIGIT_MAP.put("7", "七");
        CHINESE_DIGIT_MAP.put("8", "八");
        CHINESE_DIGIT_MAP.put("9", "九");
    }

    private SpeakerType curSpeaker = SpeakerType.WOMAN;
    private String curLan = VoiceServiceConstants.LAN_CHINESE;
    private IVoiceService.TTSListener listener;
    private TTSInitCallback initCallback;
    private boolean isInit = false;
    private ITTSEngine ttsEngine;

    public CloudTTSEngine(TTSInitCallback initCallback, ITTSEngine ttsEngine) {
        if (initCallback == null || ttsEngine == null) {
            Logger.error(TAG, "param has null");
            return;
        }
        this.initCallback = initCallback;
        this.ttsEngine = ttsEngine;

        ITTSEngine.TTSIntentParams intentParams = new ITTSEngine.TTSIntentParams();
        intentParams.setTextType(VoiceServiceConstants.TTS_TEXT_TYPE);
        intentParams.setSpeakingStyle(VoiceServiceConstants.TTS_SPEAKING_STYLE);
        intentParams.setReturnPhone(true);
        intentParams.setHighLightInfo(false);
        intentParams.setAudioType(VoiceServiceConstants.TTS_AUDIO_TYPE_WAV);
        intentParams.setSpeaker(curSpeaker.getSpeakerName());
        intentParams.setTtsServer(VoiceServiceConstants.TTS_SERVER_URL);

        ITTSEngine.TTSConfigParams configParams = new ITTSEngine.TTSConfigParams();
        configParams.setUseCache(false);
        ttsEngine.init(intentParams, configParams, new MyTTSListener());
    }

    public void setTTSListener(IVoiceService.TTSListener listener) {
        this.listener = listener;
    }

    public void setCurSpeaker(SpeakerType speakerType) {
        if (speakerType.equals(curSpeaker)) {
            return;
        }
        curSpeaker = speakerType;
        ttsEngine.setSpeaker(curSpeaker.getSpeakerName());
    }

    public void setCurLan(String lan) {
        curLan = lan;
    }

    public void speakInSpeed(String words, String id, float speed) {
        ttsEngine.start(broadcastProcess(words), id, speed);
    }

    private String broadcastProcess(String words) {
        if (words == null || words.isEmpty()) {
            return "";
        }
        String textCopy = words.toLowerCase(Locale.ROOT);
        textCopy = textCopy.trim();
        if (Objects.equals(curLan, VoiceServiceConstants.LAN_ENGLISH)) {
            textCopy = textCopy.replace("℃", "degrees");
            textCopy = textCopy.replace("2.4g", "two point four G");
            textCopy = textCopy.replace("2.4G", "two point four G");
            textCopy = textCopy.replace("5g", "five G");
            textCopy = textCopy.replace("5G", "five G");
            textCopy = processAlphanumericTokens(textCopy);
        } else {
            textCopy = processDatetime(textCopy);
            textCopy = textCopy.replaceAll("(?<=\\d)点(?=\\d)", ".");
            textCopy = textCopy.replace("2.4g", "二点四寄");
            textCopy = textCopy.replace("5g", "五寄");
            textCopy = textCopy.replace("IP", "挨批");
            textCopy = textCopy.replace("调优", "条优");
            textCopy = textCopy.replaceAll("(?<!\\d)\\B-(?=\\d)", "负");
            textCopy = textCopy.replace("Mbps", "兆每秒");
        }
        textCopy = textCopy.replaceAll("\\b(\\d{8,15})\\b", "​$1​");
        textCopy = textCopy.replace("wi-fi6", "wifi 6");
        textCopy = textCopy.replace("wi-fi", "wifi");

        String regex = "[" + VoiceServiceConstants.SPLIT_PUNCTUATIONS + "]\\n";
        textCopy = textCopy.replaceAll(regex, "\n");
        if (textCopy.isEmpty()) {
            return textCopy;
        }
        char lastChar = textCopy.charAt(textCopy.length() - 1);
        if (VoiceServiceConstants.SPLIT_PUNCTUATIONS.chars().anyMatch(ele -> lastChar == ele)) {
            textCopy = textCopy.substring(0, textCopy.length() - 1);
        }
        return textCopy;
    }

    private static String processDatetime(String input) {
        Matcher matcher = DATETIME_PATTERN.matcher(input);
        StringBuffer sb = new StringBuffer();
        while (matcher.find()) {
            String year = matcher.group(1);
            String month = matcher.group(2);
            String day = matcher.group(3);
            String hour = matcher.group(4);
            String minute = matcher.group(5);
            String chineseDatetime = digitsToChinese(year) + "年"
                    + numberToChinese(Integer.parseInt(month)) + "月"
                    + numberToChinese(Integer.parseInt(day)) + "日"
                    + numberToChinese(Integer.parseInt(hour)) + "点"
                    + formatMinute(minute);
            matcher.appendReplacement(sb, chineseDatetime);
        }
        matcher.appendTail(sb);
        return sb.toString();
    }

    private static String digitsToChinese(String digits) {
        StringBuilder sb = new StringBuilder();
        for (char c : digits.toCharArray()) {
            sb.append(CHINESE_DIGIT_MAP.getOrDefault(String.valueOf(c), String.valueOf(c)));
        }
        return sb.toString();
    }

    private static String numberToChinese(int num) {
        if (num == 0) {
            return "零";
        }
        if (num < 10) {
            return CHINESE_DIGIT_MAP.get(String.valueOf(num));
        }
        if (num == 10) {
            return "十";
        }
        if (num < 20) {
            return "十" + CHINESE_DIGIT_MAP.get(String.valueOf(num % 10));
        }
        if (num % 10 == 0) {
            return CHINESE_DIGIT_MAP.get(String.valueOf(num / 10)) + "十";
        }
        return CHINESE_DIGIT_MAP.get(String.valueOf(num / 10)) + "十"
                + CHINESE_DIGIT_MAP.get(String.valueOf(num % 10));
    }

    private static String formatMinute(String minute) {
        if (minute.equals("00")) {
            return "整";
        }
        if (minute.startsWith("0")) {
            return "零" + CHINESE_DIGIT_MAP.get(String.valueOf(minute.charAt(1))) + "分";
        }
        return numberToChinese(Integer.parseInt(minute)) + "分";
    }

    private static String processAlphanumericTokens(String input) {
        Matcher matcher = VoiceServiceConstants.ALPHANUMERIC_PATTERN.matcher(input);
        StringBuffer sb = new StringBuffer();
        while (matcher.find()) {
            String token = matcher.group();
            if (token.matches("\\d+") || token.matches("[a-zA-Z]+")) {
                matcher.appendReplacement(sb, token);
                continue;
            }
            StringBuilder replaced = new StringBuilder();
            for (char c : token.toCharArray()) {
                if (Character.isDigit(c)) {
                    replaced.append(VoiceServiceConstants.digitToWord
                                    .getOrDefault(String.valueOf(c), String.valueOf(c)))
                            .append(" ");
                } else {
                    replaced.append(c);
                }
            }
            matcher.appendReplacement(sb, replaced.toString().trim());
        }
        matcher.appendTail(sb);
        return sb.toString();
    }

    public void stopSpeaking() {
        ttsEngine.stop();
    }

    public void destroyTTS() {
        ttsEngine.destroy();
    }

    private class MyTTSListener implements ITTSEngine.TTSListener {
        @Override
        public void onInit(int status) {
            isInit = true;
            if (status == VoiceServiceConstants.OPT_SUCCESS) {
                initCallback.onInit();
            } else {
                initCallback.onInitError(status, "init tts fail!");
            }
        }

        @Override
        public void onError(String id, int errorCode, String errorDes) {
            if (!isInit) {
                isInit = true;
                initCallback.onInitError(errorCode, errorDes);
            } else {
                stopSpeaking();
                if (listener != null) {
                    listener.onTTSError(id);
                }
            }
        }

        @Override
        public void onCompletion(String id) {
            if (listener != null) {
                listener.onTTSComplete(id);
            }
        }

        @Override
        public void onProgress(int currentTime, int totalTime, boolean isRefTextTTSFinished) {
            if (listener != null) {
                listener.onTTSProgress();
            }
        }
    }

    public interface TTSInitCallback {
        void onInit();
        void onInitError(int errorCode, String errorDes);
    }
}
