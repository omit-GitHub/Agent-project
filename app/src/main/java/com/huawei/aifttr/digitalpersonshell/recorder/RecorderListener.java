package com.huawei.aifttr.digitalpersonshell.recorder;

/**
 * 录音机回调。
 */
public interface RecorderListener {
    void onRecordStarted();

    void onDataReceived(byte[] buffer, int size);

    void onRecordStopped();

    void onRecordReleased();

    void onException(Exception e);
}
