package com.huawei.aifttr.digitalpersonshell.services;

import java.util.ArrayDeque;

/**
 * 在回调发起线程上串行排空事件队列。
 * <p>不持锁执行事件；同步重入只入队，避免 ASR/TTS/WS 回调互相嵌套修改状态。</p>
 */
final class SerialEventDispatcher {
    private final ArrayDeque<Runnable> queue = new ArrayDeque<>();
    private boolean draining;

    void dispatch(Runnable event) {
        synchronized (queue) {
            queue.addLast(event);
            if (draining) {
                return;
            }
            draining = true;
        }
        while (true) {
            Runnable next;
            synchronized (queue) {
                next = queue.pollFirst();
                if (next == null) {
                    draining = false;
                    return;
                }
            }
            try {
                next.run();
            } catch (RuntimeException | Error failure) {
                synchronized (queue) {
                    queue.clear();
                    draining = false;
                }
                throw failure;
            }
        }
    }
}
