package com.guiagent.executor.commands.tencent;

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
 * 腾讯视频命令单元测试（批量）。
 */
public class TencentCommandTest {

    private GuiAgentService service;

    @Before
    public void setUp() {
        service = mock(GuiAgentService.class);
        when(service.gesture(any(), anyLong())).thenReturn(true);
    }

    // ---------- TogglePlay ----------
    @Test
    public void testTogglePlay_success() throws Exception {
        TencentTogglePlayCommand cmd = new TencentTogglePlayCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service, atLeast(2)).gesture(any(), anyLong());
    }

    @Test
    public void testTogglePlay_serviceNull() throws Exception {
        TencentTogglePlayCommand cmd = new TencentTogglePlayCommand();
        JsonObject result = cmd.execute(null, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
    }

    // ---------- NextEpisode ----------
    @Test
    public void testNextEpisode_success() throws Exception {
        TencentNextEpisodeCommand cmd = new TencentNextEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- PrevEpisode ----------
    @Test
    public void testPrevEpisode_success() throws Exception {
        TencentPrevEpisodeCommand cmd = new TencentPrevEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service).remoteKey(eq("MEDIA_PREVIOUS"), anyLong());
    }

    // ---------- ToggleControlBar ----------
    @Test
    public void testToggleControlBar_success() throws Exception {
        TencentToggleControlBarCommand cmd = new TencentToggleControlBarCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- OpenEpisodePanel ----------
    @Test
    public void testOpenEpisodePanel_success() throws Exception {
        TencentOpenEpisodePanelCommand cmd = new TencentOpenEpisodePanelCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- CloseEpisodePanel ----------
    @Test
    public void testCloseEpisodePanel_success() throws Exception {
        TencentCloseEpisodePanelCommand cmd = new TencentCloseEpisodePanelCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- ScrollEpisode ----------
    @Test
    public void testScrollUp_success() throws Exception {
        TencentScrollEpisodeUpCommand cmd = new TencentScrollEpisodeUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testScrollDown_success() throws Exception {
        TencentScrollEpisodeDownCommand cmd = new TencentScrollEpisodeDownCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- SelectEpisode ----------
    @Test
    public void testSelectEpisode_missingParam() throws Exception {
        TencentSelectEpisodeCommand cmd = new TencentSelectEpisodeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSelectEpisode_nodeFound() throws Exception {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        doAnswer(inv -> {
            Rect r = inv.getArgument(0);
            r.set(100, 200, 300, 400);
            return null;
        }).when(node).getBoundsInScreen(any(Rect.class));
        when(service.findNodes(any(Match.class))).thenReturn(Arrays.asList(node));

        TencentSelectEpisodeCommand cmd = new TencentSelectEpisodeCommand();
        JsonObject params = new JsonObject();
        params.addProperty("episode", 3);
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testSelectEpisode_nodeNotFound() throws Exception {
        when(service.findNodes(any(Match.class))).thenReturn(Collections.emptyList());

        TencentSelectEpisodeCommand cmd = new TencentSelectEpisodeCommand();
        JsonObject params = new JsonObject();
        params.addProperty("episode", 999);
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("NO_MATCH", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- SetSpeed ----------
    @Test
    public void testSetSpeed_invalidValue() throws Exception {
        TencentSetSpeedCommand cmd = new TencentSetSpeedCommand();
        JsonObject params = new JsonObject();
        params.addProperty("speed", "3.0");
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSetSpeed_validSpeed() throws Exception {
        TencentSetSpeedCommand cmd = new TencentSetSpeedCommand();
        JsonObject params = new JsonObject();
        params.addProperty("speed", "1.5");
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- SetQuality ----------
    @Test
    public void testSetQuality_invalidValue() throws Exception {
        TencentSetQualityCommand cmd = new TencentSetQualityCommand();
        JsonObject params = new JsonObject();
        params.addProperty("quality", "8K");
        JsonObject result = cmd.execute(service, params);
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", result.getAsJsonObject("error").get("code").getAsString());
    }

    @Test
    public void testSetQuality_validQuality() throws Exception {
        TencentSetQualityCommand cmd = new TencentSetQualityCommand();
        JsonObject params = new JsonObject();
        params.addProperty("quality", "480P");
        JsonObject result = cmd.execute(service, params);
        assertTrue(result.get("ok").getAsBoolean());
    }

    // ---------- Brightness ----------
    @Test
    public void testBrightnessUp_success() throws Exception {
        TencentBrightnessUpCommand cmd = new TencentBrightnessUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }

    @Test
    public void testBrightnessDown_success() throws Exception {
        TencentBrightnessDownCommand cmd = new TencentBrightnessDownCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
    }
}
