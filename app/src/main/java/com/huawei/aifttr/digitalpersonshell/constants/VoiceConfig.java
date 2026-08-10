package com.huawei.aifttr.digitalpersonshell.constants;

/**
 * 语音能力配置常量（T-005 / M-10）。
 * <p>
 * 集中唤醒词、TTS 发音人/语速、连续会话时限、云端 URL 与授权凭证。
 * 凭证沿用 Shell（本次边界内沿用，后续移至配置）；声纹相关资源不在此声明。
 */
public final class VoiceConfig {

    private VoiceConfig() {
    }

    /** 默认唤醒词。 */
    public static final String DEFAULT_WAKEUP_WORD = "你好小光";

    /** TTS 默认发音人（女声 hqqiaf，沿用源库 D-07）。 */
    public static final String DEFAULT_TTS_SPEAKER = "hqqiaf";

    /** TTS 默认语速（1.0 为正常语速）。 */
    public static final float DEFAULT_TTS_SPEED = 1.0f;

    /** 唤醒命中后 TTS 问候语（参考 DigitalPerson preset_words_greeting03）。 */
    public static final String GREETING_TEXT = "我在";

    /** ASR 无语音超时错误码（BR-004）。 */
    public static final int ASR_TIMEOUT_ERROR_CODE = 70904;

    /** 最后一段 TTS 播报结束后，无新输入时保留 Agent session 的时长。 */
    public static final long CONTINUOUS_SESSION_TIMEOUT_MS = 10_000L;

    /** ASR 云端地址。 */
    public static final String ASR_SERVER_URL = "wss://asr.dui.ai/runtime/v2/recognize";

    /** TTS 云端地址。 */
    public static final String TTS_SERVER_URL = "https://tts.duiopen.com/runtime/aggregation/synthesize";

    /** 授权服务地址。 */
    public static final String AUTH_SERVER_URL = "https://auth.duiopen.com";

    /** 授权凭证（沿用 Shell，后续移至配置）。 */
    public static final String AUTH_API_KEY = "701dbdc6cd42701dbdc6cd426a1e7fd5";
    public static final String AUTH_PRODUCT_ID = "279634786";
    public static final String AUTH_PRODUCT_KEY = "3fa284ddea1fd3f59063b082d364a8d3";
    public static final String AUTH_PRODUCT_SECRET = "e226700ad91cc31e079939c3a2f1cd52";

    /** 唤醒词模型资源名（非 vp，声纹已裁剪；匹配唤醒词"你好小光"需真机验证，D-05）。 */
    public static final String WAKEUP_RES = "wakeup_aifar_comm_20180104.bin";

    /** 本地 VAD 模型资源名。 */
    public static final String VAD_RES = "vad_aihome_v0.11.bin";

    /** AEC/beamforming 资源名（沿用 Shell 默认双麦）。 */
    public static final String SSPE_RES = "sspe_aec_ch2_mic1_ref1_asr_v2.0.0.165.bin";
}
