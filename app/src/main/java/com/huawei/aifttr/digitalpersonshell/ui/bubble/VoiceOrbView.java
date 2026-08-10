package com.huawei.aifttr.digitalpersonshell.ui.bubble;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;
import android.view.animation.LinearInterpolator;

import androidx.annotation.Nullable;

import com.huawei.aifttr.digitalpersonshell.data.model.session.ConversationPhase;

/** 轻量语音光球。只绘制 Canvas，不依赖图片资源。 */
public class VoiceOrbView extends View {

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private ValueAnimator animator;
    private float phase;
    private ConversationPhase mode = ConversationPhase.LISTENING;

    public VoiceOrbView(Context context) {
        this(context, null);
    }

    public VoiceOrbView(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        paint.setDither(true);
    }

    public void setMode(ConversationPhase mode) {
        this.mode = mode == null ? ConversationPhase.LISTENING : mode;
        invalidate();
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        animator = ValueAnimator.ofFloat(0f, (float) (Math.PI * 2));
        animator.setDuration(1800L);
        animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.setInterpolator(new LinearInterpolator());
        animator.addUpdateListener(value -> {
            phase = (float) value.getAnimatedValue();
            invalidate();
        });
        animator.start();
    }

    @Override
    protected void onDetachedFromWindow() {
        if (animator != null) {
            animator.cancel();
            animator = null;
        }
        super.onDetachedFromWindow();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        float radius = Math.min(cx, cy) * 0.72f;
        float pulse = 1f + 0.08f * (float) Math.sin(phase * speedMultiplier());

        int primary;
        int secondary;
        switch (mode) {
            case THINKING:
                primary = Color.rgb(161, 108, 255);
                secondary = Color.rgb(80, 122, 255);
                break;
            case SPEAKING:
                primary = Color.rgb(255, 91, 178);
                secondary = Color.rgb(104, 110, 255);
                break;
            case LISTENING:
            default:
                primary = Color.rgb(68, 217, 255);
                secondary = Color.rgb(94, 111, 255);
                break;
        }

        paint.setShader(new RadialGradient(cx, cy, radius * 1.35f,
                new int[]{Color.WHITE, primary, withAlpha(secondary, 36)},
                new float[]{0f, 0.45f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawCircle(cx, cy, radius * 1.35f * pulse, paint);

        paint.setShader(null);
        paint.setColor(withAlpha(primary, 105));
        float orbit = radius * 0.28f;
        canvas.drawCircle(cx + orbit * (float) Math.cos(phase),
                cy + orbit * (float) Math.sin(phase), radius * 0.42f, paint);
        paint.setColor(withAlpha(secondary, 120));
        canvas.drawCircle(cx - orbit * (float) Math.sin(phase),
                cy + orbit * (float) Math.cos(phase), radius * 0.34f, paint);
    }

    private float speedMultiplier() {
        return mode == ConversationPhase.THINKING ? 1.7f
                : mode == ConversationPhase.SPEAKING ? 2.2f : 1f;
    }

    private static int withAlpha(int color, int alpha) {
        return Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color));
    }
}
