package com.guiagent.executor;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.IBinder;
import android.os.RemoteException;

import com.stb.stbcmd.IStbCmdCallback;
import com.stb.stbcmd.IStbCmdService;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Collections;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Sends allow-listed remote-control keys through the vendor StbCmdService.
 * The vendor service executes the same input keyevent command as a physical remote.
 */
public final class DpadAdapter {
    private static final ComponentName COMPONENT = new ComponentName(
            "com.stb.settings.aidl", "com.stb.stbcmd.StbCmdService");
    private static final Map<String, Integer> KEY_CODES;

    static {
        Map<String, Integer> keys = new HashMap<>();
        keys.put("UP", 19);
        keys.put("DOWN", 20);
        keys.put("LEFT", 21);
        keys.put("RIGHT", 22);
        keys.put("ENTER", 23);
        keys.put("BACK", 4);
        keys.put("HOME", 3);
        keys.put("MENU", 82);
        keys.put("VOLUME_UP", 24);
        keys.put("VOLUME_DOWN", 25);
        keys.put("VOLUME_MUTE", 164);
        keys.put("MEDIA_PLAY_PAUSE", 85);
        keys.put("MEDIA_PLAY", 126);
        keys.put("MEDIA_PAUSE", 127);
        keys.put("MEDIA_NEXT", 87);
        keys.put("MEDIA_PREVIOUS", 88);
        keys.put("DIGIT_0", 7);
        keys.put("DIGIT_1", 8);
        keys.put("DIGIT_2", 9);
        keys.put("DIGIT_3", 10);
        keys.put("DIGIT_4", 11);
        keys.put("DIGIT_5", 12);
        keys.put("DIGIT_6", 13);
        keys.put("DIGIT_7", 14);
        keys.put("DIGIT_8", 15);
        keys.put("DIGIT_9", 16);
        KEY_CODES = Collections.unmodifiableMap(keys);
    }

    private final Context context;
    private final Object connectionLock = new Object();
    private volatile IStbCmdService service;
    private volatile boolean binding;
    private volatile long breakerUntil;
    private int consecutiveTimeouts;

    private final ServiceConnection connection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            synchronized (connectionLock) {
                service = IStbCmdService.Stub.asInterface(binder);
                binding = false;
                connectionLock.notifyAll();
            }
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            synchronized (connectionLock) {
                service = null;
                binding = false;
                connectionLock.notifyAll();
            }
        }
    };

    public DpadAdapter(Context context) {
        this.context = context.getApplicationContext();
        bind();
    }

    public synchronized JSONObject send(String key, long timeoutMs) {
        String normalized = key == null ? "" : key.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        Integer code = KEY_CODES.get(normalized);
        if (code == null) throw new Err("BAD_ARGS", "unsupported remote key: " + key);
        if (System.currentTimeMillis() < breakerUntil) {
            throw new Err("DPAD_CIRCUIT_OPEN", "remote-control service is cooling down");
        }

        IStbCmdService remote = awaitService(Math.min(timeoutMs, 2500L));
        if (remote == null) throw new Err("DPAD_UNAVAILABLE", "StbCmdService is not available");

        CountDownLatch callbackLatch = new CountDownLatch(1);
        final String[] callbackResult = {""};
        final boolean[] callbackSuccess = {false};
        IStbCmdCallback callback = new IStbCmdCallback.Stub() {
            @Override
            public void cmdFinished(String result, boolean success) {
                callbackResult[0] = result == null ? "" : result;
                callbackSuccess[0] = success;
                callbackLatch.countDown();
            }
        };

        try {
            remote.ExecCMD("input keyevent " + code, 0, callback);
            boolean completed = callbackLatch.await(Math.max(250L, timeoutMs), TimeUnit.MILLISECONDS);
            if (!completed) {
                onTimeout();
                throw new Err("DPAD_TIMEOUT", "StbCmdService did not call back");
            }
            consecutiveTimeouts = 0;
            if (!callbackSuccess[0]) {
                throw new Err("DPAD_REJECTED", callbackResult[0]);
            }
            return new JSONObject()
                    .put("key", normalized)
                    .put("keyCode", code)
                    .put("vendorResult", callbackResult[0]);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new Err("INTERRUPTED", "remote key request interrupted");
        } catch (RemoteException e) {
            service = null;
            bind();
            throw new Err("DPAD_REMOTE_ERROR", e.getMessage() == null ? "remote service error" : e.getMessage());
        } catch (JSONException e) {
            throw new Err("INTERNAL", "could not encode remote key result");
        }
    }

    public void close() {
        try {
            context.unbindService(connection);
        } catch (IllegalArgumentException ignored) {
            // The vendor service may never have bound on devices that do not provide it.
        }
        service = null;
    }

    private void onTimeout() {
        consecutiveTimeouts++;
        if (consecutiveTimeouts >= 2) {
            breakerUntil = System.currentTimeMillis() + 10_000L;
            consecutiveTimeouts = 0;
        }
    }

    private IStbCmdService awaitService(long timeoutMs) {
        if (service != null) return service;
        bind();
        long deadline = System.currentTimeMillis() + timeoutMs;
        synchronized (connectionLock) {
            while (service == null && System.currentTimeMillis() < deadline) {
                try {
                    connectionLock.wait(Math.max(1L, deadline - System.currentTimeMillis()));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return null;
                }
            }
            return service;
        }
    }

    private void bind() {
        synchronized (connectionLock) {
            if (service != null || binding) return;
            binding = true;
            Intent intent = new Intent("com.stb.aidl.IStbCmdService").setComponent(COMPONENT);
            try {
                if (!context.bindService(intent, connection, Context.BIND_AUTO_CREATE)) binding = false;
            } catch (SecurityException e) {
                binding = false;
            }
        }
    }
}
