package com.huawei.aifttr.digitalpersonshell.utils;

/**
 * Markdown 文本处理工具（T-WS / T-B 系列共用）。
 * <p>
 * 仅处理加粗标记 {@code **}/{@code __}，不动单 {@code *}/{@code _}（避免误伤 "5 * 3" 这类合法星号）。
 * 纯 Java、不 import android.*，JVM 单测可覆盖。
 */
public final class MarkdownText {

    private MarkdownText() {
    }

    /**
     * 去除 markdown 加粗标记（{@code **} 与 {@code __}），保留内部文本。
     * <p>
     * 逐段调用、不要求配对——对流式拆分的 chunk 鲁棒（如 {@code "前**ab"} / {@code "cd**后"}
     * 各自去掉 {@code **} → {@code "前ab"} / {@code "cd后"}）。用于 TTS 播报路径，避免星号被念出。
     *
     * @param s 原始文本，可为 null
     * @return 去除加粗标记后的文本，null → ""
     */
    public static String stripBold(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("**", "").replace("__", "");
    }
}
