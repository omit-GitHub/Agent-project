package com.guiagent.executor.commands.common;

import com.google.gson.JsonObject;
import com.guiagent.executor.Err;
import com.guiagent.executor.GuiAgentService;

import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/**
 * 通用命令单元测试: GoBack, GoHome, Volume*, Navigation。
 */
public class CommonCommandTest {

    private GuiAgentService service;

    @Before
    public void setUp() {
        service = mock(GuiAgentService.class);
    }

    // ---------- GoBack ----------
    @Test
    public void testGoBack_success() throws Exception {
        when(service.global(anyInt())).thenReturn(true);
        GoBackCommand cmd = new GoBackCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        assertEquals("back", result.getAsJsonObject("data").get("result").getAsString());
    }

    @Test
    public void testGoBack_serviceNull() throws Exception {
        GoBackCommand cmd = new GoBackCommand();
        JsonObject result = cmd.execute(null, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
    }

    // ---------- GoHome ----------
    @Test
    public void testGoHome_success() throws Exception {
        when(service.global(anyInt())).thenReturn(true);
        GoHomeCommand cmd = new GoHomeCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        assertEquals("home", result.getAsJsonObject("data").get("result").getAsString());
    }

    // ---------- VolumeUp ----------
    @Test
    public void testVolumeUp_success() throws Exception {
        VolumeUpCommand cmd = new VolumeUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service).remoteKey(eq("VOLUME_UP"), anyLong());
    }

    @Test
    public void testVolumeUp_dpadUnavailable() throws Exception {
        when(service.remoteKey(anyString(), anyLong())).thenThrow(new Err("DPAD_UNAVAILABLE", "not init"));
        VolumeUpCommand cmd = new VolumeUpCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("DPAD_UNAVAILABLE", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- VolumeDown ----------
    @Test
    public void testVolumeDown_success() throws Exception {
        VolumeDownCommand cmd = new VolumeDownCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service).remoteKey(eq("VOLUME_DOWN"), anyLong());
    }

    // ---------- VolumeMute ----------
    @Test
    public void testVolumeMute_success() throws Exception {
        VolumeMuteCommand cmd = new VolumeMuteCommand();
        JsonObject result = cmd.execute(service, new JsonObject());
        assertTrue(result.get("ok").getAsBoolean());
        verify(service).remoteKey(eq("VOLUME_MUTE"), anyLong());
    }
}
