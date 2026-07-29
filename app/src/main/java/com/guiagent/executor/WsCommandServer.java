package com.guiagent.executor;

import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * WebSocket 服务端(载体 C)。监听 0.0.0.0:8322,RFC 6455 握手 + 帧收发,
 * 文本帧经 {@link LineHandler} 转发(生产注入 {@code line -> Protocol.handle(svc, line)})。
 *
 * <p>设计:握手 {@link WsHandshake}、帧 {@link WsFrame}、转发 {@link LineHandler} 均为无 Android
 * 依赖的纯逻辑;本类的 {@link #frameLoop} / {@link #handleConnection} 为静态纯逻辑(JVM 可单测,不调
 * android.util.Log);accept/ServerSocket 层调 Log,走集成测试。</p>
 */
public class WsCommandServer {

    private static final String TAG = "guiagent";
    static final int DEFAULT_PORT = 8322;

    private final GuiAgentService svc;
    private final int port;
    private ServerSocket serverSocket;
    private volatile boolean running = true;

    public WsCommandServer(GuiAgentService svc) {
        this(svc, DEFAULT_PORT);
    }

    public WsCommandServer(GuiAgentService svc, int port) {
        this.svc = svc;
        this.port = port;
    }

    public void start() {
        try {
            serverSocket = new ServerSocket(port);
        } catch (IOException e) {
            Log.w(TAG, "ws bind failed :" + port + ", ws disabled", e);
            running = false;
            return;
        }
        Thread t = new Thread(this::acceptLoop, "guiagent-ws-accept");
        t.setDaemon(true);
        t.start();
        Log.i(TAG, "ws server up :" + port);
    }

    public void stop() {
        running = false;
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (Exception ignored) {
        }
    }

    private void acceptLoop() {
        while (running) {
            try {
                final Socket client = serverSocket.accept();
                Thread c = new Thread(() -> {
                    try {
                        handleConnection(client.getInputStream(), client.getOutputStream(),
                                line -> Protocol.handle(svc, line));
                    } catch (Exception e) {
                        Log.w(TAG, "ws conn err", e);
                    } finally {
                        try {
                            client.close();
                        } catch (Exception ignored) {
                        }
                    }
                }, "guiagent-ws-conn");
                c.setDaemon(true);
                c.start();
            } catch (Exception e) {
                if (running) Log.w(TAG, "ws accept failed", e);
                break;
            }
        }
    }

    // ---------- 纯逻辑(JVM 可单测,不调 android.util.Log)----------

    /** 帧循环:握手后调用。文本帧转发,ping 回 pong,close/畸形断开。 */
    static void frameLoop(InputStream in, OutputStream out, LineHandler handler) throws IOException {
        while (true) {
            WsFrame.Frame f = WsFrame.readFrame(in);
            switch (f.type) {
                case TEXT: {
                    String resp = handler.apply(f.text());
                    out.write(WsFrame.encodeText(resp));
                    out.flush();
                    break;
                }
                case PING:
                    out.write(WsFrame.encodePong(f.payload));
                    out.flush();
                    break;
                case CLOSE:
                    out.write(WsFrame.encodeClose());
                    out.flush();
                    return;
                default: // PONG / INVALID / BINARY -> 关连接,不杀主循环
                    out.write(WsFrame.encodeClose());
                    out.flush();
                    return;
            }
        }
    }

    /** 完整连接处理:握手 + 帧循环;IO 异常静默关闭。 */
    static void handleConnection(InputStream in, OutputStream out, LineHandler handler) {
        try {
            String req = readHandshake(in);
            if (!WsHandshake.validate(req)) {
                out.write("HTTP/1.1 400 Bad Request\r\n\r\n".getBytes(StandardCharsets.UTF_8));
                out.flush();
                return;
            }
            out.write(WsHandshake.buildResponse(WsHandshake.extractKey(req))
                    .getBytes(StandardCharsets.UTF_8));
            out.flush();
            frameLoop(in, out, handler);
        } catch (IOException e) {
            // 静默关闭(BR-004 / BR-007)
        }
    }

    /** 读 HTTP 请求头直到 \r\n\r\n。 */
    private static String readHandshake(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] target = {'\r', '\n', '\r', '\n'};
        int matched = 0;
        int c;
        while ((c = in.read()) != -1) {
            buf.write(c);
            if (c == target[matched]) {
                matched++;
                if (matched == 4) break;
            } else {
                matched = (c == target[0]) ? 1 : 0;
            }
        }
        return new String(buf.toByteArray(), StandardCharsets.UTF_8);
    }
}
