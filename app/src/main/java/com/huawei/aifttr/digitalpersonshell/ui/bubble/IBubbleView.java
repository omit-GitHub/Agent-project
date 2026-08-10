package com.huawei.aifttr.digitalpersonshell.ui.bubble;

import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;

/**
 * 气泡视图操作契约（T-B01 / M-B02）。
 * <p>
 * 由 {@code ChatBubblePresenter} 调用、{@code ChatBubbleController} 实现，
 * 将逻辑层指令映射为 Android 框架侧 WindowManager/Handler 操作。
 * 延迟/取消隐藏由 Controller 持有 Handler 实现，Presenter 仅发指令（NFR-B03 可测性）。
 */
public interface IBubbleView {

    /** 显示气泡面板（WindowManager.addView）。 */
    void showPanel();

    /** 隐藏气泡面板（实现负责切换到主线程）。 */
    void hidePanel();

    /** 更新语音阶段文案和光球动画。 */
    void setVoiceState(ConversationPhase state);

    /**
     * 设置用户气泡文本（主线程 Handler，BR-B09）。
     *
     * @param text 用户文本
     */
    void setUserText(String text);

    /**
     * 设置系统气泡文本（主线程 Handler + 跑马灯重启，BR-B02/B07/B09）。
     *
     * @param text 系统累加文本
     */
    void setSystemText(String text);
}
