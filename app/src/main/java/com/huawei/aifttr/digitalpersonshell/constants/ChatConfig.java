package com.huawei.aifttr.digitalpersonshell.constants;

/**
 * WebSocket 对话服务常量（T-WS-01）。
 * <p>
 * 集中 ws 协议要素（前缀/端口/路径/方法/类型/事件名）、超时与重连阈值、错误兜底语。
 * 凭证沿用 Shell，声纹相关不在本声明。
 */
public final class ChatConfig {

    private ChatConfig() {
    }

    /** WebSocket URL 前缀（明文，按需求约定）。 */
    public static final String WS_SCHEME = "ws://";

    /** WebSocket 端口。 */
    public static final String WS_PORT = "17000";

    /** WebSocket 路径 + sessionId 查询参数前缀。 */
    public static final String WS_PATH = "/ws?sessionId=";

    /** 请求方法：发送对话。 */
    public static final String METHOD_CHAT_SEND = "chat.send";

    /** 请求类型。 */
    public static final String REQ_TYPE = "req";

    /** 响应事件名：流式增量。 */
    public static final String EVENT_STREAM_DELTA = "stream.delta";

    /** 响应事件名：本轮对话结束。 */
    public static final String EVENT_STREAM_END = "stream.done";

    /** 顶层 key。 */
    public static final String KEY_EVENT = "event";
    public static final String KEY_PAYLOAD = "payload";
    public static final String KEY_DELTA = "delta";
    public static final String KEY_MSG_ID = "msgId";
    public static final String KEY_SEQ = "seq";

    /** 消息响应超时（秒）。 */
    public static final long TIMEOUT_SECONDS = 30L;

    /** 错误兜底播报语。 */
    public static final String ERROR_FALLBACK_TEXT = "出错了，请稍后再试";
}
