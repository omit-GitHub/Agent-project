package com.huawei.aifttr.digitalpersonshell.sdk.impl;

import com.huawei.aifttr.digitalpersonshell.constants.VoiceConfig;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.WakeupConfigSpec;
import com.huawei.aifttr.digitalpersonshell.sdk.impl.WakeupEngineHelper;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

/**
 * WakeupEngineHelper 唤醒去声纹配置测试（TC-006 / SC-004/011 / BR-007/008）。
 * <p>
 * WakeupEngineHelper 的 DUI config 构建逻辑通过纯 Java {@link WakeupConfigSpec}
 * 暴露为可测缝（JVM 无法构造真实 DUI 引擎），验证应用到 DUI 的
 * implVprintCutCk 固定为 false，不向声纹透传裁剪音频。
 */
public class WakeupEngineHelperTest {

    @Test
    public void config_setsImplVprintCutCkFalse() {
        WakeupConfigSpec spec = WakeupEngineHelper.buildWakeupConfig();

        assertFalse("implVprintCutCk 必须为 false（BR-008）", spec.isImplVprintCutCk());
        assertEquals("唤醒词映射拼音", "ni hao xiao guang", spec.getWakeupWords()[0]);
        assertEquals("唤醒模型为不带 vp 资源", VoiceConfig.WAKEUP_RES, spec.getWakeupResource());
    }
}
