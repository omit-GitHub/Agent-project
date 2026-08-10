package com.huawei.aifttr.digitalpersonshell.constants;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * 语音服务常量（声纹裁剪后 ENGINE_INIT_NUM 5→4）。
 */
public final class VoiceServiceConstants {
    /** 引擎初始化数量（ASR/VAD/Wakeup/TTS，声纹已裁剪）。 */
    public static final int ENGINE_INIT_NUM = 4;

    public static final int ASR_ENGINE_INDEX = 0;
    public static final int VAD_ENGINE_INDEX = 1;
    public static final int WAKEUP_ENGINE_INDEX = 2;
    public static final int TTS_ENGINE_INDEX = 3;

    public static final String INIT_NO_PERMISSION_CODE = "-1";
    public static final String INIT_SPEECH_NULL_CODE = "-2";
    public static final String INIT_ENGINE_ERROR_CODE = "-3";

    public static final int TYPE_COMMON_DUAL = 1;
    public static final int TYPE_COMMON_LINE4 = 2;
    public static final int TYPE_COMMON_ECHO = 4;

    public static final String ASR_RESOURCE_TYPE = "aihome";
    public static final String ASR_WAKEUP_WORD = "ni hao xiao guang";

    public static final int OPT_SUCCESS = 0;
    public static final int ASR_STATE_RUNNING = 2;
    public static final int ASR_END_FLAG = 1;
    public static final int ASR_JSON_ERROR = -1;
    public static final int ASR_NO_SPEECH_TIMEOUT = 5000;
    public static final int ASR_SPEECH_NOT_STOP_TIMEOUT = 500;
    public static final int ASR_TIMEOUT_ERROR_CODE = 70904;

    public static final String TTS_TEXT_TYPE = "text";
    public static final String TTS_SPEAKING_STYLE = "happy";
    public static final String TTS_AUDIO_TYPE_WAV = "wav";

    public static final int INIT_ASR_CACHE_LEN = 16000 * 2;
    public static final int MAX_ASR_CACHE_LEN = 5 * 16000 * 2;

    public static final String SPLIT_PUNCTUATIONS = ",.，。;；？！?!\n\t";

    public static final Pattern ALPHANUMERIC_PATTERN =
            Pattern.compile("\\b[a-zA-Z][a-zA-Z0-9`'_\\-\\.]*[0-9][a-zA-Z0-9`'_\\-\\.]*\\b|"
                    + "\\b[0-9][a-zA-Z0-9`'_\\-\\.]*[a-zA-Z][a-zA-Z0-9`'_\\-\\.]*\\b");

    public static final String LAN_CHINESE = "简体中文";
    public static final String LAN_ENGLISH = "English";

    public static Map<String, String> digitToWord = new HashMap<>();
    public static Set<Character> punctuations =
            new HashSet<>(Arrays.asList('.', '?', '!', ',', ';', ':', '。', '？', '！', '，', '；', '：'));
    public static Map<Integer, String> indexToEngine = new HashMap<>();

    /** 云端 ASR 地址（运行期可被 SpeechProvider 覆盖）。 */
    public static final String ASR_SERVER_URL = "wss://asr.dui.ai/runtime/v2/recognize";
    /** 云端 TTS 地址（运行期可被 SpeechProvider 覆盖）。 */
    public static final String TTS_SERVER_URL = "https://tts.duiopen.com/runtime/aggregation/synthesize";

    static {
        digitToWord.put("0", "zero");
        digitToWord.put("1", "one");
        digitToWord.put("2", "two");
        digitToWord.put("3", "three");
        digitToWord.put("4", "four");
        digitToWord.put("5", "five");
        digitToWord.put("6", "six");
        digitToWord.put("7", "seven");
        digitToWord.put("8", "eight");
        digitToWord.put("9", "nine");

        indexToEngine.put(ASR_ENGINE_INDEX, "ASR ");
        indexToEngine.put(VAD_ENGINE_INDEX, "VAD ");
        indexToEngine.put(WAKEUP_ENGINE_INDEX, "Wakeup ");
        indexToEngine.put(TTS_ENGINE_INDEX, "TTS ");
    }

    private VoiceServiceConstants() {
    }
}
