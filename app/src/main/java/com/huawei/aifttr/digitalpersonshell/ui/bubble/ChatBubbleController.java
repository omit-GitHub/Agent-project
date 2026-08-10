package com.huawei.aifttr.digitalpersonshell.ui.bubble;

import android.content.Context;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.Spannable;
import android.text.SpannableStringBuilder;
import android.text.style.StyleSpan;
import android.util.DisplayMetrics;
import android.view.LayoutInflater;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;

import com.huawei.aifttr.digitalpersonshell.R;
import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 对话气泡视图层（T-B04 / M-B04）。
 * <p>
 * 实现 {@link IBubbleView} 的 Android 框架侧：WindowManager addView/removeView 悬浮面板、
 * 主线程 Handler 更新 TextView、延迟/取消隐藏、跑马灯 setSelected(true)。
 * 逻辑全部在 {@link ChatBubblePresenter}，本类仅承接视图指令（NFR-B03 可测性）。
 * <p>
 * 悬浮窗权限未授权时静默跳过 UI，不阻断语音链路（BR-B08）。
 */
public class ChatBubbleController implements IBubbleView {

    private static final String TAG = "ChatBubbleController";
    /** 面板宽度占屏宽比例（需求 60–70%，取 65%）。 */
    private static final float WIDTH_RATIO = 0.65f;

    private final Context context;
    private final WindowManager windowManager;
    private final Handler mainHandler;

    private TextView userTv;
    private TextView systemTv;
    private TextView statusTv;
    private VoiceOrbView voiceOrb;
    private View userMessageGroup;
    private View assistantMessageGroup;

    private View inflatedPanel;
    private boolean added = false;

    public ChatBubbleController(Context context) {
        this.context = context;
        this.windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        this.mainHandler = new Handler(Looper.getMainLooper());
    }

    private View ensurePanel() {
        if (inflatedPanel == null) {
            LayoutInflater inflater = LayoutInflater.from(context);
            inflatedPanel = inflater.inflate(R.layout.view_chat_bubbles, null);
            userTv = inflatedPanel.findViewById(R.id.tv_user_bubble);
            systemTv = inflatedPanel.findViewById(R.id.tv_system_bubble);
            statusTv = inflatedPanel.findViewById(R.id.tv_voice_status);
            voiceOrb = inflatedPanel.findViewById(R.id.voice_orb);
            userMessageGroup = inflatedPanel.findViewById(R.id.user_message_group);
            assistantMessageGroup = inflatedPanel.findViewById(R.id.assistant_message_group);
        }
        return inflatedPanel;
    }

    @Override
    public void showPanel() {
        mainHandler.post(this::showPanelOnMain);
    }

    private void showPanelOnMain() {
        // 悬浮窗权限守卫：未授权静默跳过，不阻断语音（BR-B08）
        if (!canDrawOverlays()) {
            Logger.warn(TAG, "[BUBBLE] 悬浮窗权限未授权，跳过气泡显示");
            return;
        }
        if (added) {
            return;
        }
        try {
            View panel = ensurePanel();
            WindowManager.LayoutParams params = buildParams();
            windowManager.addView(panel, params);
            added = true;
            Logger.info(TAG, "[BUBBLE] 气泡面板已显示");
        } catch (Exception e) {
            Logger.error(TAG, "[BUBBLE] showPanel 失败（真机路径不应至此）", e);
        }
    }

    @Override
    public void hidePanel() {
        mainHandler.post(this::hidePanelOnMain);
    }

    private void hidePanelOnMain() {
        if (!added || inflatedPanel == null) {
            return;
        }
        try {
            windowManager.removeView(inflatedPanel);
        } catch (Exception e) {
            Logger.error(TAG, "[BUBBLE] hidePanel 失败", e);
        } finally {
            added = false;
        }
    }

    @Override
    public void setVoiceState(ConversationPhase state) {
        mainHandler.post(() -> {
            if (statusTv == null || voiceOrb == null) {
                return;
            }
            int label;
            switch (state) {
                case THINKING:
                    label = R.string.voice_status_thinking;
                    break;
                case SPEAKING:
                    label = R.string.voice_status_speaking;
                    break;
                case LISTENING:
                default:
                    label = R.string.voice_status_listening;
                    break;
            }
            statusTv.setText(label);
            voiceOrb.setMode(state);
        });
    }

    @Override
    public void setUserText(String text) {
        postMessageText(userTv, userMessageGroup, singleLine(text));
    }

    @Override
    public void setSystemText(String text) {
        // 系统气泡渲染 markdown 加粗：**x** → 粗体 x（去掉 ** 标记）
        postMessageText(systemTv, assistantMessageGroup, renderBold(singleLine(text)));
    }

    /** 释放资源：移除未触发的延迟隐藏 + overlay view（VFS.onDestroy 调用）。 */
    public void release() {
        hidePanel();
    }

    private void postMessageText(TextView tv, View group, CharSequence text) {
        if (tv == null || group == null) {
            return;
        }
        // 两个角色各占一行，超长文本分别横向滚动。
        mainHandler.post(() -> {
            tv.setText(text);
            boolean visible = text != null && text.length() > 0;
            group.setVisibility(visible ? View.VISIBLE : View.GONE);
            tv.setSelected(visible);
        });
    }

    /** 语音浮层只占一行：把 Agent 格式化输出中的换行折叠成单个空格。 */
    private static String singleLine(String text) {
        return text == null ? "" : text.replaceAll("\\s*[\\r\\n]+\\s*", " ").trim();
    }

    /** ** 加粗标记正则：配对 **x** → x 粗体。非贪婪，避免跨段误吞。 */
    private static final Pattern BOLD_PATTERN = Pattern.compile("\\*\\*(.+?)\\*\\*");

    /**
     * 把 markdown 加粗 {@code **x**}
     * <p>
     * 用 SpannableStringBuilder 手工构建，避免 {@code Html.fromHtml} 的 {@code <}/{@code &} 转义坑；
     * 未配对的 {@code **}（流式中途）保持原样，下一段 delta 全量重渲染闭合后即正确。
     *
     * @param text 原始累加文本
     * @return 渲染后的 CharSequence，无加粗标记时原样返回
     */
    private static CharSequence renderBold(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        Matcher m = BOLD_PATTERN.matcher(text);
        if (!m.find()) {
            return text;
        }
        SpannableStringBuilder sb = new SpannableStringBuilder();
        m.reset();
        int last = 0;
        while (m.find()) {
            sb.append(text, last, m.start());
            int boldStart = sb.length();
            sb.append(m.group(1));
            sb.setSpan(new StyleSpan(Typeface.BOLD), boldStart, sb.length(),
                    Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            last = m.end();
        }
        sb.append(text, last, text.length());
        return sb;
    }

    private WindowManager.LayoutParams buildParams() {
        // minSdk 28 ≥ O，直接用应用层 overlay 类型（NFR-B04）
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                computeWidth(),
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        params.gravity = android.view.Gravity.BOTTOM | android.view.Gravity.CENTER_HORIZONTAL;
        params.y = (int) context.getResources().getDimension(R.dimen.voice_panel_margin_bottom);
        return params;
    }

    /** 屏宽 65%（推断）。 */
    private int computeWidth() {
        DisplayMetrics dm = context.getResources().getDisplayMetrics();
        return (int) (dm.widthPixels * WIDTH_RATIO);
    }

    private boolean canDrawOverlays() {
        return Settings.canDrawOverlays(context);
    }
}
