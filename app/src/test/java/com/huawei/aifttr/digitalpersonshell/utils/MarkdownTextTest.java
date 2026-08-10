package com.huawei.aifttr.digitalpersonshell.utils;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

/**
 * {@link MarkdownText#stripBold} 单测。
 */
public class MarkdownTextTest {

    @Test
    public void stripBold_pairedBold() {
        assertEquals("你好", MarkdownText.stripBold("**你好**"));
    }

    @Test
    public void stripBold_pairedUnderscore() {
        assertEquals("你好", MarkdownText.stripBold("__你好__"));
    }

    @Test
    public void stripBold_splitChunk_firstHalf() {
        // 流式第一段：未闭合的 ** 也要去掉
        assertEquals("前ab", MarkdownText.stripBold("前**ab"));
    }

    @Test
    public void stripBold_splitChunk_secondHalf() {
        // 流式第二段：开头残留的 ** 去掉
        assertEquals("cd后", MarkdownText.stripBold("cd**后"));
    }

    @Test
    public void stripBold_singleAsteriskPreserved() {
        // 单星号不是加粗标记，保留
        assertEquals("5 * 3 = 15", MarkdownText.stripBold("5 * 3 = 15"));
    }

    @Test
    public void stripBold_singleUnderscorePreserved() {
        assertEquals("a_b", MarkdownText.stripBold("a_b"));
    }

    @Test
    public void stripBold_mixedBoldAndPlain() {
        assertEquals("结果是 重要数据 结束", MarkdownText.stripBold("结果是 **重要数据** 结束"));
    }

    @Test
    public void stripBold_nullReturnsEmpty() {
        assertEquals("", MarkdownText.stripBold(null));
    }

    @Test
    public void stripBold_empty() {
        assertEquals("", MarkdownText.stripBold(""));
    }
}
