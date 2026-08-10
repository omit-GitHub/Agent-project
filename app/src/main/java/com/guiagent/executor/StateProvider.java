package com.guiagent.executor;

import com.google.gson.JsonObject;

/**
 * 状态采集提供者。注入 CompoundRegistry，使命令执行后可自动附加前台状态；
 * JVM 单测中用 fake 替换，隔离 Android 依赖。
 */
public interface StateProvider {

    /** 立即采集当前前台状态 {pkg, summary}；服务不可用时返回 null。 */
    JsonObject capture();

    /** 等待页面稳定后采集（见 StateCapture.awaitStable）；服务不可用时返回 null。 */
    JsonObject awaitStable(String baselinePkg, long capMs);
}
