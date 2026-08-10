package com.huawei.aifttr.digitalpersonshell.services.interfaces;

/**
 * 对外语音服务接口（IBaseVoiceServices + IMediumVoiceService 合并产物，声纹方法已裁剪）。
 * <p>
 * 精简为「唤醒→ASR→TTS」三回调编排：init 后注册唤醒/ASR/TTS 监听，
 * 唤醒命中由内部 one-shot 联动 ASR；调用方通过 startASR/stopASR、startTTS/cancelTTS 控制。
 * 不含聊天/弹窗/WebSocket 等业务耦合。
 *
 * @see VoiceConfig
 */
public interface IVoiceService {

    /**
     * 初始化语音模块（授权 + 4 引擎 init）。
     *
     * @param callback 初始化结果回调
     */
    void init(InitCallback callback);

    /**
     * 设置唤醒监听。唤醒命中后由实现内部 one-shot 联动 startASR（BR-003）。
     */
    void setWakeupListener(WakeupListener listener);

    /**
     * 设置 ASR 监听。
     */
    void setASRListener(ASRListener listener);

    /**
     * 设置 TTS 监听。
     */
    void setTTSListener(TTSListener listener);

    /** 设置 TTS 播报期间的用户插话监听。 */
    void setBargeInListener(BargeInListener listener);

    /**
     * 设置唤醒词，默认 "你好小光"。
     */
    void setWakeupWord(String wakeupWord);

    /**
     * 开始语音识别（外部主动触发，或唤醒 one-shot 内部触发）。
     */
    long startASR();

    /**
     * 取消语音识别。
     */
    void stopASR();

    /**
     * 启动仅做本地语音起点检测的拾音；检测到开口后实现层原地切换到 ASR。
     *
     * @return 录音源初始化并成功进入监听时返回 true；否则调用方应退回唤醒词打断
     */
    boolean startBargeInDetection();

    /** 停止尚未触发的插话检测；若已切换为 ASR 则不影响当前识别。 */
    void stopBargeInDetection();

    /**
     * 开始语音播报。
     *
     * @param text  播报文本
     * @param id    播报 id
     * @param speed 语速（1.0 为正常语速）
     */
    void startTTS(String text, String id, float speed);

    /**
     * 取消语音播报，立即释放播放（BR-006）。
     */
    void cancelTTS();

    /**
     * 销毁语音模块。
     */
    void destroy();

    /**
     * 初始化结果回调。
     */
    interface InitCallback {
        void onSuccess();

        void onError(String errorCode, String errorInfo);
    }

    /**
     * 唤醒监听。
     */
    interface WakeupListener {
        /**
         * 检测到唤醒词。
         *
         * @param confidence  置信度
         * @param wakeupWord  命中的唤醒词
         */
        void onWakeup(double confidence, String wakeupWord);
    }

    /**
     * ASR 监听。
     */
    interface ASRListener {
        /** ASR 已检测到用户开口；用于立即停止空闲 session 计时。 */
        void onASRSpeechStart(long asrId);

        /**
         * 语音识别结果。
         *
         * @param words      识别文本
         * @param audio      语音音源（仅调试用，不参与声纹处理，BR-009）
         * @param isFinished 当前这段语音是否结束
         */
        void onASRResult(long asrId, String words, byte[] audio, boolean isFinished);

        /**
         * 语音识别错误。无语音超时返回 70904（BR-004）。
         */
        void onASRError(long asrId, int errorCode, String errorInfo);
    }

    interface BargeInListener {
        /** 检测到用户在 TTS 播报期间开口；回调返回后实现层会启动云端 ASR。 */
        void onBargeIn(long asrId);
    }

    /**
     * TTS 监听。
     */
    interface TTSListener {
        void onTTSProgress();

        void onTTSComplete(String id);

        void onTTSError(String id);
    }
}
