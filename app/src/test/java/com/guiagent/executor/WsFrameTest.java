package com.guiagent.executor;

import java.nio.charset.StandardCharsets;
import org.junit.Test;
import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * WsFrame 单元测试(T-002)。纯逻辑,无 Android 依赖,JVM 跑。
 * 覆盖 RFC 6455 基础帧:掩码文本解码、文本编码、close/ping 识别、畸形帧拒绝。
 */
public class WsFrameTest {

    // RFC 6455 §5.7 掩码 "Hello" 文本帧
    private static final byte[] HELLO_MASKED = new byte[]{
            (byte) 0x81, (byte) 0x85, 0x37, (byte) 0xFA, 0x21, 0x3D,
            0x7F, (byte) 0x9F, 0x4D, 0x51, 0x58
    };

    // TC-006: 解掩码文本帧 -> "Hello", opcode=TEXT
    @Test
    public void testDecodeMaskedTextFrame_hello() {
        WsFrame.Frame f = WsFrame.decode(HELLO_MASKED);
        assertEquals(WsFrame.Type.TEXT, f.type);
        assertEquals("Hello", f.text());
    }

    // TC-007: 文本帧编码往返(服务端不掩码),decode(requireMask=false) 解回原文
    @Test
    public void testEncodeTextFrame_roundTrip() {
        String line = "{\"id\":\"1\",\"op\":\"ping\",\"args\":{}}";
        byte[] enc = WsFrame.encodeText(line);
        // 服务端帧 mask bit 必须为 0(BR-005)
        assertEquals("server frame must be unmasked", 0, (enc[1] >>> 7) & 1);
        WsFrame.Frame f = WsFrame.decode(enc, false);
        assertEquals(WsFrame.Type.TEXT, f.type);
        assertEquals(line, f.text());
    }

    // TC-008: close 帧识别
    @Test
    public void testDecode_closeFrame_returnsClose() {
        byte[] close = new byte[]{(byte) 0x88, (byte) 0x80, 0, 0, 0, 0};
        assertEquals(WsFrame.Type.CLOSE, WsFrame.decode(close).type);
    }

    // TC-009: ping 帧识别
    @Test
    public void testDecode_pingFrame_returnsPing() {
        byte[] ping = new byte[]{(byte) 0x89, (byte) 0x80, 0, 0, 0, 0};
        assertEquals(WsFrame.Type.PING, WsFrame.decode(ping).type);
    }

    // TC-010: 客户端帧 mask bit=0 -> 畸形(客户端→服务端必须掩码)
    @Test
    public void testDecode_unmaskedClientFrame_rejected() {
        byte[] unmasked = new byte[]{(byte) 0x81, 0x05, 'H', 'e', 'l', 'l', 'o'};
        assertEquals(WsFrame.Type.INVALID, WsFrame.decode(unmasked).type);
    }

    // TC-011: 声明载荷 > 256KiB -> 畸形
    @Test
    public void testDecode_oversizedFrame_rejected() {
        // 0x81 0xFF(mask=1,len=127) + 8 字节长度 0x0000000000040001 = 262145 > 262144
        byte[] big = new byte[]{
                (byte) 0x81, (byte) 0xFF,
                0, 0, 0, 0, 0, 4, 0, 1
        };
        assertEquals(WsFrame.Type.INVALID, WsFrame.decode(big).type);
    }

    // TC-012: 二进制 opcode 0x2 -> 非文本,畸形
    @Test
    public void testDecode_binaryFrame_rejected() {
        byte[] bin = new byte[]{
                (byte) 0x82, (byte) 0x82, 0, 0, 0, 0, 'a', 'b'
        };
        assertEquals(WsFrame.Type.INVALID, WsFrame.decode(bin).type);
    }

    // 补充:encodeText 短帧字节结构(FIN+TEXT, len=5, 原文 payload)
    @Test
    public void testEncodeText_helloBytes() {
        assertArrayEquals(
                new byte[]{(byte) 0x81, 0x05, 'H', 'e', 'l', 'l', 'o'},
                WsFrame.encodeText("Hello")
        );
    }
}
