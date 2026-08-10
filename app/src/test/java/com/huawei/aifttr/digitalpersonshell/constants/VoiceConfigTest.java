package com.huawei.aifttr.digitalpersonshell.constants;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import com.huawei.aifttr.digitalpersonshell.constants.VoiceConfig;

/**
 * VoiceConfig 配置常量测试（T-005 / BR-005/006）。
 */
public class VoiceConfigTest {

    @Test
    public void defaults_areSet() {
        assertEquals("唤醒词默认应为 你好小光", "你好小光", VoiceConfig.DEFAULT_WAKEUP_WORD);
        assertEquals("TTS 发音人默认应为 hqqiaf", "hqqiaf", VoiceConfig.DEFAULT_TTS_SPEAKER);
        assertEquals("TTS 语速默认应为 1.0", 1.0f, VoiceConfig.DEFAULT_TTS_SPEED, 0.0001f);

        // 凭证与云端 URL 非空（沿用 Shell 凭证）
        assertNotNull("授权 apiKey 非空", VoiceConfig.AUTH_API_KEY);
        assertTrue("授权 apiKey 不为空串", !VoiceConfig.AUTH_API_KEY.isEmpty());
        assertNotNull("授权 productId 非空", VoiceConfig.AUTH_PRODUCT_ID);
        assertNotNull("授权 productKey 非空", VoiceConfig.AUTH_PRODUCT_KEY);
        assertNotNull("授权 productSecret 非空", VoiceConfig.AUTH_PRODUCT_SECRET);
        assertNotNull("ASR 云端 URL 非空", VoiceConfig.ASR_SERVER_URL);
        assertNotNull("TTS 云端 URL 非空", VoiceConfig.TTS_SERVER_URL);
        assertNotNull("授权服务 URL 非空", VoiceConfig.AUTH_SERVER_URL);
    }
}
