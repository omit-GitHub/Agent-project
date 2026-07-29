package com.guiagent.executor;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * RFC 6455 基础帧编解码(纯逻辑,无 Android 依赖,JVM 可单测)。
 * - decode: 解客户端掩码文本帧、识别 close/ping/pong/binary、校验掩码与载荷上限。
 * - encodeText: 服务端不掩码文本帧。
 * - readFrame: 从 InputStream 流式读一帧(委托 decode,集成层)。
 */
public final class WsFrame {

    static final int OP_TEXT = 0x1;
    static final int OP_BINARY = 0x2;
    static final int OP_CLOSE = 0x8;
    static final int OP_PING = 0x9;
    static final int OP_PONG = 0xA;

    /** 单帧载荷上限(BR-009),超限判畸形。 */
    static final int MAX_PAYLOAD = 256 * 1024;

    private WsFrame() {
    }

    enum Type {TEXT, BINARY, CLOSE, PING, PONG, INVALID}

    static final class Frame {
        final Type type;
        final byte[] payload;

        Frame(Type type, byte[] payload) {
            this.type = type;
            this.payload = payload;
        }

        /** TEXT 帧的 UTF-8 文本;非 TEXT 返回空串。 */
        String text() {
            return type == Type.TEXT ? new String(payload, StandardCharsets.UTF_8) : "";
        }
    }

    /** 解整帧字节,客户端帧必须带掩码(requireClientMask=true)。 */
    static Frame decode(byte[] raw) {
        return decode(raw, true);
    }

    /** 解整帧字节。requireClientMask=false 用于解析服务端帧(测试往返)。 */
    static Frame decode(byte[] raw, boolean requireClientMask) {
        if (raw.length < 2) return new Frame(Type.INVALID, EMPTY);
        int b0 = raw[0] & 0xff;
        int b1 = raw[1] & 0xff;
        int opcode = b0 & 0x0f;
        boolean mask = (b1 & 0x80) != 0;
        long len = b1 & 0x7f;

        int off = 2;
        if (len == 126) {
            if (raw.length < 4) return new Frame(Type.INVALID, EMPTY);
            len = ((raw[2] & 0xff) << 8) | (raw[3] & 0xff);
            off = 4;
        } else if (len == 127) {
            if (raw.length < 10) return new Frame(Type.INVALID, EMPTY);
            len = 0;
            for (int i = 2; i < 10; i++) {
                len = (len << 8) | (raw[i] & 0xff);
            }
            off = 10;
        }
        if (len > MAX_PAYLOAD) return new Frame(Type.INVALID, EMPTY);
        if (requireClientMask && !mask) return new Frame(Type.INVALID, EMPTY);

        byte[] maskKey = null;
        if (mask) {
            if (raw.length < off + 4) return new Frame(Type.INVALID, EMPTY);
            maskKey = new byte[4];
            System.arraycopy(raw, off, maskKey, 0, 4);
            off += 4;
        }
        if (raw.length < off + len) return new Frame(Type.INVALID, EMPTY);
        byte[] payload = new byte[(int) len];
        System.arraycopy(raw, off, payload, 0, (int) len);
        if (mask) {
            for (int i = 0; i < payload.length; i++) {
                payload[i] ^= maskKey[i & 3];
            }
        }
        switch (opcode) {
            case OP_TEXT:
                return new Frame(Type.TEXT, payload);
            case OP_CLOSE:
                return new Frame(Type.CLOSE, payload);
            case OP_PING:
                return new Frame(Type.PING, payload);
            case OP_PONG:
                return new Frame(Type.PONG, payload);
            default:
                return new Frame(Type.INVALID, payload); // BINARY 等非文本 -> 畸形
        }
    }

    /** 构造服务端不掩码文本帧。 */
    static byte[] encodeText(String text) {
        byte[] payload = text.getBytes(StandardCharsets.UTF_8);
        return encode(OP_TEXT, payload);
    }

    /** 构造服务端 pong 帧(回 ping)。 */
    static byte[] encodePong(byte[] pingPayload) {
        return encode(OP_PONG, pingPayload);
    }

    /** 构造服务端 close 帧(空载荷)。 */
    static byte[] encodeClose() {
        return encode(OP_CLOSE, EMPTY);
    }

    private static final byte[] EMPTY = new byte[0];

    /** 服务端帧编码(FIN=1, 不掩码)。 */
    private static byte[] encode(int opcode, byte[] payload) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(0x80 | opcode); // FIN + opcode
        int n = payload.length;
        if (n <= 125) {
            out.write(n);
        } else if (n <= 0xFFFF) {
            out.write(126);
            out.write((n >>> 8) & 0xff);
            out.write(n & 0xff);
        } else {
            out.write(127);
            for (int i = 7; i >= 0; i--) {
                out.write((n >>> (i * 8)) & 0xff);
            }
        }
        out.write(payload, 0, payload.length);
        return out.toByteArray();
    }

    /** 从 InputStream 流式读一帧(集成层用)。 */
    static Frame readFrame(InputStream in) throws IOException {
        int b0 = in.read();
        if (b0 < 0) return new Frame(Type.INVALID, EMPTY);
        int b1 = in.read();
        if (b1 < 0) return new Frame(Type.INVALID, EMPTY);
        boolean mask = (b1 & 0x80) != 0;
        long len = b1 & 0x7f;

        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        buf.write(b0);
        buf.write(b1);
        if (len == 126) {
            for (int i = 0; i < 2; i++) buf.write(readOrFail(in));
            len = ((buf.toByteArray()[2] & 0xff) << 8) | (buf.toByteArray()[3] & 0xff);
        } else if (len == 127) {
            for (int i = 0; i < 8; i++) buf.write(readOrFail(in));
            len = 0;
            byte[] h = buf.toByteArray();
            for (int i = 2; i < 10; i++) len = (len << 8) | (h[i] & 0xff);
        }
        if (len > MAX_PAYLOAD) return new Frame(Type.INVALID, EMPTY);
        if (mask) {
            for (int i = 0; i < 4; i++) buf.write(readOrFail(in));
        }
        for (long i = 0; i < len; i++) buf.write(readOrFail(in));
        return decode(buf.toByteArray());
    }

    private static int readOrFail(InputStream in) throws IOException {
        int v = in.read();
        if (v < 0) throw new IOException("unexpected eof");
        return v;
    }
}
