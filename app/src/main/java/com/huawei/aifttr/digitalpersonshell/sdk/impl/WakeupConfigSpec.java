package com.huawei.aifttr.digitalpersonshell.sdk.impl;

/**
 * 唤醒配置规格（纯 Java，不引用 DUI 类型，作为 WakeupEngineHelper 的可测缝）。
 * <p>
 * WakeupEngineHelper 将此规格应用到 DUI 的 AILocalSignalAndWakeupConfig，
 * 其中 {@link #isImplVprintCutCk()} 固定为 false（BR-008，不向声纹透传裁剪音频）。
 */
public final class WakeupConfigSpec {
    private final String wakeupResource;
    private final String sspeResource;
    private final String[] wakeupWords;
    private final int[] majors;
    private final float[] thresholds;
    private final boolean implVprintCutCk;

    public WakeupConfigSpec(String wakeupResource, String sspeResource,
                            String[] wakeupWords, int[] majors, float[] thresholds,
                            boolean implVprintCutCk) {
        this.wakeupResource = wakeupResource;
        this.sspeResource = sspeResource;
        this.wakeupWords = wakeupWords;
        this.majors = majors;
        this.thresholds = thresholds;
        this.implVprintCutCk = implVprintCutCk;
    }

    public String getWakeupResource() { return wakeupResource; }
    public String getSspeResource() { return sspeResource; }
    public String[] getWakeupWords() { return wakeupWords; }
    public int[] getMajors() { return majors; }
    public float[] getThresholds() { return thresholds; }

    /**
     * 是否启用声纹裁剪音频透传。固定 false（BR-008）。
     */
    public boolean isImplVprintCutCk() { return implVprintCutCk; }
}
