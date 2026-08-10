package com.huawei.aifttr.digitalpersonshell.data.model.enums;

/**
 * 发音人类型。
 */
public enum SpeakerType {
    WOMAN("hqqiaf"),
    MAN("brettmp");

    private final String speakerName;

    SpeakerType(String speakerName) {
        this.speakerName = speakerName;
    }

    public String getSpeakerName() {
        return speakerName;
    }
}
