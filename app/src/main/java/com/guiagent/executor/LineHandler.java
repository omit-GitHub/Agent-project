package com.guiagent.executor;

/**
 * 一行 NDJSON -> 一行 NDJSON 响应的转发接口(函数式)。
 * 解耦 WsCommandServer 与 Protocol:生产注入 {@code line -> Protocol.handle(svc, line)},
 * 测试注入 mock,使转发逻辑可在 JVM 单测、不依赖 Android framework。
 */
@FunctionalInterface
public interface LineHandler {
    String apply(String line);
}
