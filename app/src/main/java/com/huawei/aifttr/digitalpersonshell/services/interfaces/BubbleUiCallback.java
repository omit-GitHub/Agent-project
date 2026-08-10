package com.huawei.aifttr.digitalpersonshell.services.interfaces;

import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationUiModel;

/**
 * 对话气泡 UI 回调契约（T-B01 / M-B01）。
 * <p>
 * 由会话协调器输出完整不可变快照，Presenter 不持有第二套会话状态。
 */
public interface BubbleUiCallback {
    /** 渲染完整快照；每次调用均覆盖旧 UI。 */
    void render(ConversationUiModel model);
}
