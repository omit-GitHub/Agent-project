package com.huawei.aifttr.digitalpersonshell.recorder;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Android 标准录音机。
 */
public class Recorder implements IRecorder {
    private static final String TAG = Recorder.class.getSimpleName();

    private static final int MICTYPE_4MIC_2CH = 4;
    private static final int MICTYPE_VOICE_COMMUNICATION = 5;

    private volatile AudioRecord mAudioRecorder;
    private RecorderListener listener;
    private final ExecutorService mThreadPool = Executors.newSingleThreadExecutor();
    private final Lock reentrantLock = new ReentrantLock();
    private volatile boolean isRecording = false;
    /** 区分连续对话中的多次 start/stop，保证旧采集循环不会在重启后复活。 */
    private volatile long recordingGeneration = 0;
    private int intervalTime = 32;
    private int audioSource = MediaRecorder.AudioSource.VOICE_RECOGNITION;
    private int sampleRate = 16000;
    private int channel = 1;
    private int format = AudioFormat.ENCODING_PCM_16BIT;
    private int micType = 1;

    @Override
    public void create(int audioSource, int sampleRate, int channel, int format, int bufferSizeInBytes) {
        this.audioSource = audioSource;
        this.sampleRate = sampleRate;
        this.channel = channel;
        this.format = format;
        try {
            mAudioRecorder = new AudioRecord(audioSource, sampleRate, channel, format, bufferSizeInBytes);
        } catch (Exception e) {
            Logger.error(TAG, "audio record error!", e);
        }
    }

    @Override
    public void create(int type) {
        Logger.info(TAG, "create: " + type);
        micType = type;
        channel = AudioFormat.CHANNEL_IN_STEREO;
        if (type == 1) {
            channel = AudioFormat.CHANNEL_IN_MONO;
            create(MediaRecorder.AudioSource.VOICE_RECOGNITION, 16000, channel,
                    AudioFormat.ENCODING_PCM_16BIT, calculateReadBufferSize());
        } else if (type == 2) {
            create(MediaRecorder.AudioSource.VOICE_RECOGNITION, 16000,
                    AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_16BIT,
                    calculateReadBufferSize());
        } else if (type == 0) {
            create(MediaRecorder.AudioSource.MIC, 16000, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO,
                            AudioFormat.ENCODING_PCM_16BIT));
        } else if (type == MICTYPE_4MIC_2CH) {
            create(MediaRecorder.AudioSource.VOICE_RECOGNITION, 16000,
                    AudioFormat.CHANNEL_IN_STEREO, AudioFormat.ENCODING_PCM_16BIT,
                    calculateReadBufferSize());
        } else if (type == MICTYPE_VOICE_COMMUNICATION) {
            channel = AudioFormat.CHANNEL_IN_MONO;
            create(MediaRecorder.AudioSource.VOICE_COMMUNICATION, 16000, channel,
                    AudioFormat.ENCODING_PCM_16BIT,
                    AudioRecord.getMinBufferSize(16000, channel, AudioFormat.ENCODING_PCM_16BIT));
        } else {
            create(MediaRecorder.AudioSource.VOICE_RECOGNITION, 32000,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    calculateReadBufferSize());
        }
        if (mAudioRecorder == null) {
            Logger.info(TAG, "create mAudioRecorder  fail ");
        } else {
            Logger.info(TAG, "create audio status : " + mAudioRecorder.getState());
        }
    }

    /**
     * 创建系统通话拾音源。AZ102u-10 的 audio_effects.xml 会为该源自动挂载 AEC + NS。
     */
    public boolean createVoiceCommunication() {
        create(MICTYPE_VOICE_COMMUNICATION);
        return mAudioRecorder != null && mAudioRecorder.getState() == AudioRecord.STATE_INITIALIZED;
    }

    public boolean isRecording() {
        return isRecording;
    }

    @Override
    public void start(RecorderListener listener) {
        reentrantLock.lock();
        try {
            if (isRecording) {
                Logger.info(TAG, "[VOICE] Recorder.start ignored: already recording");
                return;
            }
            this.listener = listener;
            if (mAudioRecorder == null) {
                create(micType);
            }
            if (mAudioRecorder == null || mAudioRecorder.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IllegalStateException("AudioRecord is not initialized");
            }
            mAudioRecorder.startRecording();
            isRecording = true;
            long generation = ++recordingGeneration;
            if (this.listener != null) {
                this.listener.onRecordStarted();
            }
            mThreadPool.execute(new RecordRunnable(generation));
        } catch (RuntimeException e) {
            isRecording = false;
            recordingGeneration++;
            Logger.error(TAG, "[VOICE] Recorder.start failed", e);
            if (this.listener != null) {
                this.listener.onException(e);
            }
        } finally {
            reentrantLock.unlock();
        }
    }

    @Override
    public void stop() {
        reentrantLock.lock();
        try {
            if (!isRecording) {
                return;
            }
            if (listener != null) {
                listener.onRecordStopped();
            }
            isRecording = false;
            recordingGeneration++;
            if (mAudioRecorder != null
                    && mAudioRecorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                mAudioRecorder.stop();
            }
        } finally {
            reentrantLock.unlock();
        }
    }

    @Override
    public void release() {
        reentrantLock.lock();
        try {
            stop();
            if (mAudioRecorder != null) {
                mAudioRecorder.release();
                mAudioRecorder = null;
            }
            if (listener != null) {
                listener.onRecordReleased();
                listener = null;
            }
            mThreadPool.shutdownNow();
        } finally {
            reentrantLock.unlock();
        }
    }

    private class RecordRunnable implements Runnable {
        private final long generation;

        RecordRunnable(long generation) {
            this.generation = generation;
        }

        @Override
        public void run() {
            if (mAudioRecorder == null) {
                create(micType);
            }
            int size = 6144;
            byte[] buffer = new byte[size];
            while (true) {
                if (!isRecording || generation != recordingGeneration) {
                    break;
                }
                int readSize = mAudioRecorder.read(buffer, 0, size);
                if (readSize > 0 && generation == recordingGeneration) {
                    byte[] bytes = new byte[readSize];
                    System.arraycopy(buffer, 0, bytes, 0, readSize);
                    if (listener != null) {
                        listener.onDataReceived(bytes, readSize);
                    }
                } else if (readSize < 0) {
                    RecorderListener current = listener;
                    if (current != null) {
                        current.onException(new IllegalStateException(
                                "AudioRecord.read failed: " + readSize));
                    }
                    break;
                }
            }
        }
    }

    private int calculateReadBufferSize() {
        int channelNumber = 1;
        switch (channel) {
            case AudioFormat.CHANNEL_IN_STEREO:
                channelNumber = 2;
                break;
            case 4:
            case 204:
                channelNumber = 4;
                break;
            case 6:
            case 252:
                channelNumber = 6;
                break;
            case AudioFormat.CHANNEL_IN_MONO:
            default:
                break;
        }
        int bytesPerSample = format == AudioFormat.ENCODING_PCM_16BIT ? 2 : 1;
        return sampleRate * channelNumber * bytesPerSample * intervalTime / 1000;
    }
}
