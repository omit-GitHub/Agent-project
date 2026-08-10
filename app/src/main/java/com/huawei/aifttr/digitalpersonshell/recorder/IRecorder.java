package com.huawei.aifttr.digitalpersonshell.recorder;

/**
 * 录音机接口。
 */
public interface IRecorder {
    void create(int type);

    void create(int audioSource, int sampleRate, int channel, int format, int bufferSizeInBytes);

    void start(RecorderListener listener);

    void stop();

    void release();
}
