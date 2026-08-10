package com.guiagent.executor;

import com.google.gson.JsonObject;

import org.junit.Before;
import org.junit.Test;

import java.util.List;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/**
 * CompoundRegistry 单元测试。
 * Mock CompoundCommand 隔离注册/分发/错误封装逻辑。
 */
public class CompoundRegistryTest {

    private CompoundRegistry registry;

    @Before
    public void setUp() {
        registry = new CompoundRegistry();
    }

    // ---------- TC-009: 注册命令后 execute 返回成功 ----------
    @Test
    public void testExecute_registeredCommand_returnsSuccess() throws Exception {
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("test_cmd");
        JsonObject expectedResult = new JsonObject();
        expectedResult.addProperty("ok", true);
        expectedResult.add("data", new JsonObject());
        when(cmd.execute(any(), any())).thenReturn(expectedResult);

        registry.register(cmd);
        JsonObject result = registry.execute("test_cmd", new JsonObject());

        assertTrue(result.get("ok").getAsBoolean());
        verify(cmd).execute(any(), any());
    }

    // ---------- TC-010: execute 未注册命令返回 UNKNOWN_COMMAND ----------
    @Test
    public void testExecute_unknownCommand_returnsUnknownCommand() {
        JsonObject result = registry.execute("foo_bar", new JsonObject());

        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("UNKNOWN_COMMAND", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- TC-011: listCommands 返回所有命令名 ----------
    @Test
    public void testListCommands_returnsAllRegistered() {
        CompoundCommand cmd1 = mock(CompoundCommand.class);
        when(cmd1.getName()).thenReturn("cmd_a");
        CompoundCommand cmd2 = mock(CompoundCommand.class);
        when(cmd2.getName()).thenReturn("cmd_b");

        registry.register(cmd1);
        registry.register(cmd2);

        List<String> commands = registry.listCommands();
        assertEquals(2, commands.size());
        assertTrue(commands.contains("cmd_a"));
        assertTrue(commands.contains("cmd_b"));
    }

    // ---------- TC-010b: 命令抛异常返回 EXECUTION_FAILED ----------
    @Test
    public void testExecute_commandThrows_returnsExecutionFailed() throws Exception {
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("bad_cmd");
        when(cmd.execute(any(), any())).thenThrow(new RuntimeException("something broke"));

        registry.register(cmd);
        JsonObject result = registry.execute("bad_cmd", new JsonObject());

        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("EXECUTION_FAILED", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- 状态附加（StateProvider 注入） ----------

    private StateProvider fakeProvider() {
        StateProvider p = mock(StateProvider.class);
        JsonObject state = new JsonObject();
        state.addProperty("pkg", "com.example.app");
        state.add("summary", new com.google.gson.JsonArray());
        when(p.capture()).thenReturn(state);
        when(p.awaitStable(anyString(), anyLong())).thenReturn(state);
        return p;
    }

    @Test
    public void testExecute_success_attachesStateToData() throws Exception {
        CompoundRegistry r = new CompoundRegistry(15, fakeProvider());
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("ok_cmd");
        when(cmd.execute(any(), any())).thenReturn(CompoundResponse.success("ok_cmd", "done"));
        r.register(cmd);

        JsonObject result = r.execute("ok_cmd", new JsonObject());

        assertTrue(result.get("ok").getAsBoolean());
        JsonObject state = result.getAsJsonObject("data").getAsJsonObject("state");
        assertNotNull(state);
        assertEquals("com.example.app", state.get("pkg").getAsString());
        r.shutdown();
    }

    @Test
    public void testExecute_error_attachesStateTopLevel() throws Exception {
        CompoundRegistry r = new CompoundRegistry(15, fakeProvider());
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("fail_cmd");
        when(cmd.execute(any(), any())).thenReturn(CompoundResponse.error("NO_MATCH", "not found"));
        r.register(cmd);

        JsonObject result = r.execute("fail_cmd", new JsonObject());

        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("NO_MATCH", result.getAsJsonObject("error").get("code").getAsString());
        assertEquals("com.example.app", result.getAsJsonObject("state").get("pkg").getAsString());
        r.shutdown();
    }

    @Test
    public void testExecute_dataWithSummary_skipsState() throws Exception {
        CompoundRegistry r = new CompoundRegistry(15, fakeProvider());
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("state_cmd");
        JsonObject data = new JsonObject();
        data.add("summary", new com.google.gson.JsonArray());
        when(cmd.execute(any(), any())).thenReturn(CompoundResponse.successWithData("state_cmd", data));
        r.register(cmd);

        JsonObject result = r.execute("state_cmd", new JsonObject());

        assertFalse(result.getAsJsonObject("data").has("state"));
        r.shutdown();
    }

    @Test
    public void testExecute_nullProvider_noStateNoCrash() throws Exception {
        CompoundRegistry r = new CompoundRegistry(15, null);
        CompoundCommand cmd = mock(CompoundCommand.class);
        when(cmd.getName()).thenReturn("plain_cmd");
        when(cmd.execute(any(), any())).thenReturn(CompoundResponse.success("plain_cmd", "done"));
        r.register(cmd);

        JsonObject result = r.execute("plain_cmd", new JsonObject());

        assertTrue(result.get("ok").getAsBoolean());
        assertFalse(result.getAsJsonObject("data").has("state"));
        r.shutdown();
    }
}
