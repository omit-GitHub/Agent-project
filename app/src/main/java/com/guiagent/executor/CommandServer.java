package com.guiagent.executor;

import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import android.util.Log;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

/**
 * 本地抽象命名空间 socket 服务(abstract namespace "guiagent")。
 * 仅本机进程可达;PC 经 `adb forward tcp:8321 localabstract:guiagent` 桥接。
 * 一行请求(NDJSON)对应一行响应。连接异常不杀主 accept 循环。
 */
public class CommandServer {

    private static final String TAG = "guiagent";
    static final String NAME = "guiagent";

    private final GuiAgentService svc;
    private final LocalServerSocket serverSocket;
    private volatile boolean running = true;

    public CommandServer(GuiAgentService svc) throws java.io.IOException {
        this.svc = svc;
        // String 构造:前导 '@' = 抽象命名空间,socket 名 "guiagent"
        this.serverSocket = new LocalServerSocket("@" + NAME);
    }

    public void start() {
        Thread t = new Thread(this::acceptLoop, "guiagent-accept");
        t.setDaemon(true);
        t.start();
    }

    public void stop() {
        running = false;
        try {
            serverSocket.close();
        } catch (Exception ignored) {
        }
    }

    private void acceptLoop() {
        while (running) {
            try {
                final LocalSocket client = serverSocket.accept();
                Thread c = new Thread(() -> handle(client), "guiagent-conn");
                c.setDaemon(true);
                c.start();
            } catch (Exception e) {
                if (running) Log.w(TAG, "accept failed", e);
                break;
            }
        }
    }

    private void handle(LocalSocket client) {
        PrintWriter pw = null;
        try {
            BufferedReader br = new BufferedReader(
                    new InputStreamReader(client.getInputStream(), StandardCharsets.UTF_8));
            pw = new PrintWriter(
                    new OutputStreamWriter(client.getOutputStream(), StandardCharsets.UTF_8), true);
            while (running) {
                String line = br.readLine();
                if (line == null) break;
                String resp = Protocol.handle(svc, line);
                pw.println(resp);
            }
        } catch (Exception e) {
            Log.w(TAG, "conn err", e);
        } finally {
            try {
                if (pw != null) pw.close();
            } catch (Exception ignored) {
            }
            try {
                client.close();
            } catch (Exception ignored) {
            }
        }
    }
}
