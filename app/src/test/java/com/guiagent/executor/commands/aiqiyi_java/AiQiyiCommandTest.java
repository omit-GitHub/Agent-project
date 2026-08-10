package com.guiagent.executor.commands.aiqiyi;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonObject;
import com.guiagent.executor.GuiAgentService;
import com.guiagent.executor.Match;

import org.junit.Before;
import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/**
 * 爱奇艺命令单元测试（批量）。
 */
public class AiQiyiCommandTest {

    private GuiAgentService service;

    @Before
    public void setUp() {
        service = mock(GuiAgentService.class);
        when(service.gesture(any(), anyLong())).thenReturn(true);
    }

    // ---------- NextEpisode ----------
    @Test
    public void testNextEpisode_success() throws Exception {
        AiQiyiNextEpisodeCommand cmd = new AiQiyiNextEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        // 验证至少 2 次 tap (wake + next)
        verify(service, atLeast(2)).gesture(any(), anyLong());
    }

    // ---------- PrevEpisode ----------
    @Test
    public void testPrevEpisode_success() throws Exception {
        AiQiyiPrevEpisodeCommand cmd = new AiQiyiPrevEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service).remoteKey(eq("MEDIA_PREVIOUS"), anyLong());
    }

    // ---------- ToggleControlBar ----------
    @Test
    public void testToggleControlBar_success() throws Exception {
        AiQiyiToggleControlBarCommand cmd = new AiQiyiToggleControlBarCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service, times(1)).gesture(any(), anyLong());
    }

    // ---------- OpenEpisodePanel ----------
    @Test
    public void testOpenEpisodePanel_success() throws Exception {
        // Mock findNodes 返回非空（验证 episodeGridView 存在）
        AccessibilityNodeInfo mockNode = mock(AccessibilityNodeInfo.class);
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(mockNode));

        AiQiyiOpenEpisodePanelCommand cmd = new AiQiyiOpenEpisodePanelCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        assertEquals("panel_opened", result.getAsJsonObject("data").get("result").getAsString());
        // 验证 2 次 tap (wake + episode btn)
        verify(service, atLeast(2)).gesture(any(), anyLong());
    }

    // ---------- CloseEpisodePanel ----------
    @Test
    public void testCloseEpisodePanel_success() throws Exception {
        AiQiyiCloseEpisodePanelCommand cmd = new AiQiyiCloseEpisodePanelCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- ScrollEpisode ----------
    @Test
    public void testScrollUp_success() throws Exception {
        AiQiyiScrollEpisodeUpCommand cmd = new AiQiyiScrollEpisodeUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testScrollDown_success() throws Exception {
        AiQiyiScrollEpisodeDownCommand cmd = new AiQiyiScrollEpisodeDownCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- SelectEpisode ----------
    @Test
    public void testSelectEpisode_missingParam() throws Exception {
        AiQiyiSelectEpisodeCommand cmd = new AiQiyiSelectEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSelectEpisode_nodeFound() throws Exception {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        Rect bounds = new Rect(100, 200, 300, 400);
        doAnswer(inv -> {
            Rect r = inv.getArgument(0);
            r.set(100, 200, 300, 400);
            return null;
        }).when(node).getBoundsInScreen(any(Rect.class));
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(node));

        AiQiyiSelectEpisodeCommand cmd = new AiQiyiSelectEpisodeCommand();
        JsonObject params = new JsonObject();
        params.addProperty("episode", 5);
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testSelectEpisode_nodeNotFound() throws Exception {
        when(service.findNodes(any(Match.class))).thenReturn(Collections.emptyList());

        AiQiyiSelectEpisodeCommand cmd = new AiQiyiSelectEpisodeCommand();
        JsonObject params = new JsonObject();
        params.addProperty("episode", 999);
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("NO_MATCH", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- SetSpeed ----------
    @Test
    public void testSetSpeed_invalidValue() throws Exception {
        AiQiyiSetSpeedCommand cmd = new AiQiyiSetSpeedCommand();
        JsonObject params = new JsonObject();
        params.addProperty("speed", "3.0");
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSetSpeed_missingParam() throws Exception {
        AiQiyiSetSpeedCommand cmd = new AiQiyiSetSpeedCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSetSpeed_validSpeed() throws Exception {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        doAnswer(inv -> {
            Rect r = inv.getArgument(0);
            r.set(100, 200, 300, 400);
            return null;
        }).when(node).getBoundsInScreen(any(Rect.class));
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(node));

        AiQiyiSetSpeedCommand cmd = new AiQiyiSetSpeedCommand();
        JsonObject params = new JsonObject();
        params.addProperty("speed", "1.5");
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- SetQuality ----------
    @Test
    public void testSetQuality_invalidValue() throws Exception {
        AiQiyiSetQualityCommand cmd = new AiQiyiSetQualityCommand();
        JsonObject params = new JsonObject();
        params.addProperty("quality", "8K");
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSetQuality_validQuality() throws Exception {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        doAnswer(inv -> {
            Rect r = inv.getArgument(0);
            r.set(100, 200, 300, 400);
            return null;
        }).when(node).getBoundsInScreen(any(Rect.class));
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(node));

        AiQiyiSetQualityCommand cmd = new AiQiyiSetQualityCommand();
        JsonObject params = new JsonObject();
        params.addProperty("quality", "1080P");
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- Brightness ----------
    @Test
    public void testBrightnessUp_success() throws Exception {
        AiQiyiBrightnessUpCommand cmd = new AiQiyiBrightnessUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testBrightnessDown_success() throws Exception {
        AiQiyiBrightnessDownCommand cmd = new AiQiyiBrightnessDownCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }
}
