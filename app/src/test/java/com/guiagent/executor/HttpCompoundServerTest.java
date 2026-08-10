package com.guiagent.executor;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/**
 * HttpCompoundServer 单元测试。
 * 使用真实 ServerSocket HTTP Server（随机空闲端口），Mock CompoundRegistry 隔离 HTTP 层逻辑。
 */
public class HttpCompoundServerTest {

    private HttpCompoundServer server;
    private CompoundRegistry registry;
    private int port;

    @Before
    public void setUp() throws Exception {
        port = findFreePort();
        registry = mock(CompoundRegistry.class);
        server = new HttpCompoundServer(port, registry);
        server.start();
        // 等待 server 启动完成
        Thread.sleep(100);
    }

    @After
    public void tearDown() {
        if (server != null) server.stop();
    }

    // ---------- TC-001: 正常 POST 请求路由到 Registry 并返回 200 ----------
    @Test
    public void testHandleCompound_validPost_returns200() throws Exception {
        JsonObject expectedResult = CompoundResponse.success("toggle_play", "toggled");
        when(registry.execute(eq("toggle_play"), any())).thenReturn(expectedResult);

        HttpURLConnection conn = postJson("/v1/compound",
                "{\"command\":\"toggle_play\",\"params\":{}}");

        assertEquals(200, conn.getResponseCode());
        String body = readBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertTrue(result.get("ok").getAsBoolean());
        assertEquals("toggle_play", result.getAsJsonObject("data").get("command").getAsString());
    }

    // ---------- TC-002: 中文（多字节 UTF-8）body 不阻塞、参数完整路由 ----------
    // 回归：Content-Length 是字节数，曾按字符数读 body 导致中文请求阻塞到客户端断开
    @Test(timeout = 10000)
    public void testHandleCompound_chineseBody_returns200() throws Exception {
        JsonObject expectedResult = CompoundResponse.success("search", "ok");
        when(registry.execute(eq("search"), argThat(p -> p != null && p.has("keyword")
                && "药神".equals(p.get("keyword").getAsString())))).thenReturn(expectedResult);

        HttpURLConnection conn = postJson("/v1/compound",
                "{\"command\":\"search\",\"params\":{\"keyword\":\"药神\"}}");
        conn.setReadTimeout(8000);

        assertEquals(200, conn.getResponseCode());
        String body = readBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertTrue(result.get("ok").getAsBoolean());
        verify(registry).execute(eq("search"), any());
    }

    // ---------- TC-002: GET /v1/compound 返回 405 ----------
    @Test
    public void testHandleCompound_getMethod_returns405() throws Exception {
        HttpURLConnection conn = get("/v1/compound");

        assertEquals(405, conn.getResponseCode());
        String body = readErrorBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertFalse(result.get("ok").getAsBoolean());
        assertEquals("METHOD_NOT_ALLOWED", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- TC-003: 非法 JSON body 返回 400 BAD_JSON ----------
    @Test
    public void testHandleCompound_invalidJson_returns400BadJson() throws Exception {
        HttpURLConnection conn = postJson("/v1/compound", "{invalid json");

        assertEquals(400, conn.getResponseCode());
        String body = readErrorBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertEquals("BAD_JSON", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- TC-004: 无 command 字段返回 400 ----------
    @Test
    public void testHandleCompound_missingCommand_returns400() throws Exception {
        HttpURLConnection conn = postJson("/v1/compound", "{\"params\":{\"episode\":5}}");

        assertEquals(400, conn.getResponseCode());
        String body = readErrorBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertEquals("BAD_JSON", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- TC-005: 未知路径返回 404 ----------
    @Test
    public void testHandleUnknownPath_returns404() throws Exception {
        HttpURLConnection conn = get("/v1/unknown");

        assertEquals(404, conn.getResponseCode());
    }

    // ---------- TC-006: GET /v1/health 返回 200 + 命令列表 ----------
    @Test
    public void testHandleHealth_returns200WithCommands() throws Exception {
        List<String> cmds = Arrays.asList("toggle_play", "next_episode", "go_back");
        when(registry.listCommands()).thenReturn(cmds);

        HttpURLConnection conn = get("/v1/health");

        assertEquals(200, conn.getResponseCode());
        String body = readBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertTrue(result.get("ok").getAsBoolean());
        JsonObject data = result.getAsJsonObject("data");
        assertEquals("healthy", data.get("status").getAsString());
    }

    // ---------- TC-007: POST /v1/health 返回 405 ----------
    @Test
    public void testHandleHealth_postMethod_returns405() throws Exception {
        HttpURLConnection conn = postJson("/v1/health", "{}");

        assertEquals(405, conn.getResponseCode());
        String body = readErrorBody(conn);
        JsonObject result = JsonParser.parseString(body).getAsJsonObject();
        assertEquals("METHOD_NOT_ALLOWED", result.getAsJsonObject("error").get("code").getAsString());
    }

    // ---------- TC-008: 端口占用时不崩溃 ----------
    @Test
    public void testStart_portOccupied_doesNotCrash() throws Exception {
        int occupiedPort = findFreePort();
        ServerSocket blocker = new ServerSocket(occupiedPort);
        try {
            HttpCompoundServer server2 = new HttpCompoundServer(occupiedPort, registry);
            server2.start();  // 应该内部捕获 IOException，不崩溃
            // 停止 server2（如果启动成功）
            server2.stop();
        } finally {
            blocker.close();
        }
        // 如果走到这里说明没有未捕获异常，测试通过
    }

    // ---------- helpers ----------

    private static int findFreePort() throws IOException {
        try (ServerSocket s = new ServerSocket(0)) {
            return s.getLocalPort();
        }
    }

    private HttpURLConnection postJson(String path, String json) throws Exception {
        URL url = new URL("http://localhost:" + port + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        conn.setDoOutput(true);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(json.getBytes(StandardCharsets.UTF_8));
        }
        return conn;
    }

    private HttpURLConnection get(String path) throws Exception {
        URL url = new URL("http://localhost:" + port + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        return conn;
    }

    private String readBody(HttpURLConnection conn) throws Exception {
        try (InputStream is = conn.getInputStream()) {
            return readStream(is);
        }
    }

    private String readErrorBody(HttpURLConnection conn) throws Exception {
        try (InputStream is = conn.getErrorStream()) {
            return is != null ? readStream(is) : "";
        }
    }

    private String readStream(InputStream is) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        byte[] buf = new byte[1024];
        int len;
        while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
        return baos.toString("UTF-8");
    }
}
