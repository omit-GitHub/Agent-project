package com.guiagent.executor;

import com.google.gson.JsonObject;

/**
 * 生产环境 StateProvider：基于 StateCapture + 当前 GuiAgentService 单例。
 * 服务不可用（如 JVM 单测环境）时返回 null，调用方跳过状态附加。
 */
public class GuiStateProvider implements StateProvider {

    @Override
    public JsonObject capture() {
        GuiAgentService service = GuiAgentService.get();
        return service == null ? null : StateCapture.capture(service);
    }

    @Override
    public JsonObject awaitStable(String baselinePkg, long capMs) {
        GuiAgentService service = GuiAgentService.get();
        return service == null ? null : StateCapture.awaitStable(service, baselinePkg, capMs);
    }
}
