package com.guiagent.executor;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import org.junit.Test;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verify;

/**
 * WsCommandServer 单元测试(T-003)。仅测纯逻辑(frameLoop 转发、handleConnection IO 容错)。
 * accept/ServerSocket 层走集成测试(DT-001/003/006)。
 */
public class WsCommandServerTest {

    private static final String LINE = "{\"id\":\"1\",\"op\":\"ping\",\"args\":{}}";
    private static final String RESP = "{\"id\":\"1\",\"ok\":true,\"data\":{\"pong\":true}}";

    /** 把服务端不掩码帧改造成客户端掩码帧(mask key 全 0,故 payload 不变),用于喂 frameLoop。仅 len<=125 档。 */
    private static byte[] toMaskedClientFrame(byte[] unmasked) {
        byte[] masked = new byte[unmasked.length + 4];
        masked[0] = unmasked[0];
        masked[1] = (byte) (unmasked[1] | 0x80); // 置 mask 位
        // mask key 4 字节全 0 -> payload XOR 0 = payload 不变
        System.arraycopy(unmasked, 2, masked, 6, unmasked.length - 2);
        return masked;
    }

    // TC-013: 收文本帧 -> 调 LineHandler -> 回文本帧
    @Test
    public void testHandleFrame_forwardsLineAndReturnsResponse() throws Exception {
        byte[] masked = toMaskedClientFrame(WsFrame.encodeText(LINE));
        InputStream in = new ByteArrayInputStream(masked);
        ByteArrayOutputStream out = new ByteArrayOutputStream();

        LineHandler handler = mock(LineHandler.class);
        when(handler.apply(LINE)).thenReturn(RESP);

        WsCommandServer.frameLoop(in, out, handler);

        verify(handler).apply(LINE);
        // out 含响应文本帧(后跟 close 帧,decode 只解首帧)
        WsFrame.Frame resp = WsFrame.decode(out.toByteArray(), false);
        assertEquals(WsFrame.Type.TEXT, resp.type);
        assertEquals(RESP, resp.text());
    }

    // TC-014: 流抛 IOException 时 handleConnection 静默关闭,不外抛
    @Test
    public void testHandleConnection_ioException_closesQuietly() throws Exception {
        InputStream in = mock(InputStream.class);
        when(in.read()).thenThrow(new IOException("reset"));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        LineHandler handler = mock(LineHandler.class);

        try {
            WsCommandServer.handleConnection(in, out, handler);
        } catch (Exception e) {
            fail("handleConnection must swallow IOException, but threw: " + e);
        }
    }
}
