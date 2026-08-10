package com.huawei.aifttr.digitalpersonshell.services.interfaces;

import org.junit.Test;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

import static org.junit.Assert.assertFalse;

import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;

/**
 * IVoiceService 接口契约测试（TC-002 / BR-007）。
 * <p>
 * 声纹识别已裁剪，IVoiceService（IBaseVoiceServices + IMediumVoiceService 合并产物）
 * 不得包含任何声纹方法。
 */
public class IVoiceServiceContractTest {

    /**
     * 被裁剪的 6 个声纹方法名（含 setVP*Callback 系列）。
     */
    private static final String[] VOICE_PRINT_METHODS = {
            "registerVoicePrint",
            "identifyVoicePrint",
            "feedVoicePrintData",
            "deleteVoicePrint",
            "setVPCreateCallback",
            "setVPDeleteCallback",
            "setVPIdentifyCallback"
    };

    @Test
    public void voiceService_hasNoVoicePrintMethods() {
        Class<?> iface = IVoiceService.class;
        List<String> declared = Arrays.stream(iface.getDeclaredMethods())
                .map(Method::getName)
                .collect(Collectors.toList());

        for (String forbidden : VOICE_PRINT_METHODS) {
            assertFalse("IVoiceService 不得包含声纹方法: " + forbidden
                            + "，实际声明: " + declared,
                    declared.contains(forbidden));
        }
    }
}
