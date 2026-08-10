package com.guiagent.executor.commands.aiqiyi;

import com.google.gson.JsonObject;

import org.junit.Before;
import org.junit.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import com.guiagent.executor.GuiAgentService;
import com.guiagent.executor.Match;

/**
 * AiQiyiTogglePlayCommand 单元测试。
 * Mock GuiAgentService 隔离爱奇艺播放/暂停逻辑。
 *
 * 逻辑（参考 aiqiyi/run-toggle.py）:
 * 1. tap 屏幕顶部中心唤出控制条
 * 2. sleep 800ms
 * 3. click_node(id=btn_pause) 精确点击
 * 4. 失败则 tap 坐标兜底
 */
public class AiQiyiTogglePlayCommandTest {

    private GuiAgentService service;
    private AiQiyiTogglePlayCommand command;

    @Before
    public void setUp() {
        service = mock(GuiAgentService.class);
        command = new AiQiyiTogglePlayCommand();
    }

    // ---------- TC-012: click_node 成功 → 返回 toggled ----------
    @Test
    public void testExecute_clickNodeSuccess_returnsToggled() throws Exception {
        // Mock root() 返回非 null（ping 需要）
        when(service.getPackageName()).thenReturn("com.qiyi.video.speaker");

        // Mock findNodes 返回一个可点击节点（btn_pause）
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        when(node.isClickable()).thenReturn(true);
        when(node.performAction(anyInt())).thenReturn(true);
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(node));

        // Mock gesture (tap) 返回 true
        when(service.gesture(any(), anyLong())).thenReturn(true);

        JsonObject result = command.execute(service, new JsonObject());

        assertTrue(result.get("ok").getAsBoolean());
        assertEquals("aiqiyi.toggle_play", result.getAsJsonObject("data").get("command").getAsString());

        // 验证至少调用了 gesture (tap 唤醒控制条)
        verify(service, atLeastOnce()).gesture(any(), anyLong());
    }

    // ---------- TC-012b: click_node 失败 → 坐标 tap 兜底 ----------
    @Test
    public void testExecute_clickNodeFails_fallbackToTap() throws Exception {
        when(service.getPackageName()).thenReturn("com.qiyi.video.speaker");

        // Mock findNodes 返回空列表（click_node 失败）
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList());

        // Mock gesture (tap) 返回 true
        when(service.gesture(any(), anyLong())).thenReturn(true);

        JsonObject result = command.execute(service, new JsonObject());

        // 兜底也应该返回成功
        assertTrue(result.get("ok").getAsBoolean());
        // 验证调用了多次 gesture（唤醒控制条 + 兜底 tap）
        verify(service, atLeast(2)).gesture(any(), anyLong());
    }

    // ---------- TC-013: service 为 null 时返回错误 ----------
    @Test
    public void testExecute_serviceNull_returnsError() throws Exception {
        JsonObject result = command.execute(null, new JsonObject());

        assertFalse(result.get("ok").getAsBoolean());
    }
}
