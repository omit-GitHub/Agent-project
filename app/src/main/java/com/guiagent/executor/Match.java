package com.guiagent.executor;

/** 节点匹配条件:任一字段非空即参与判定(AND 关系);子串匹配,id 比对末段。 */
public class Match {
    public final String text;
    public final String id;
    public final String desc;
    public final String cls;
    public final Integer limit;

    public Match(String text, String id, String desc, String cls, Integer limit) {
        this.text = text;
        this.id = id;
        this.desc = desc;
        this.cls = cls;
        this.limit = limit;
    }

    @Override
    public String toString() {
        return "{text=" + text + ",id=" + id + ",desc=" + desc + ",cls=" + cls + ",limit=" + limit + "}";
    }
}
