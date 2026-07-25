package com.guiagent.executor;

/** 协议错误:固定 code,供响应 err.code。 */
public class Err extends RuntimeException {
    public final String code;

    public Err(String code, String msg) {
        super(msg);
        this.code = code;
    }
}
