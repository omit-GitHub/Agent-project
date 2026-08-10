package com.huawei.aifttr.digitalpersonshell.services;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class SerialEventDispatcherTest {

    @Test
    public void reentrantDispatch_queuesNestedEventAfterCurrentEvent() {
        SerialEventDispatcher dispatcher = new SerialEventDispatcher();
        List<String> order = new ArrayList<>();

        dispatcher.dispatch(() -> {
            order.add("outer-start");
            dispatcher.dispatch(() -> order.add("nested"));
            order.add("outer-end");
        });

        assertEquals(Arrays.asList("outer-start", "outer-end", "nested"), order);
    }

    @Test
    public void failedEvent_clearsQueuedWorkAndDispatcherCanBeReused() {
        SerialEventDispatcher dispatcher = new SerialEventDispatcher();
        List<String> events = new ArrayList<>();

        try {
            dispatcher.dispatch(() -> {
                dispatcher.dispatch(() -> events.add("stale"));
                throw new IllegalStateException("boom");
            });
            fail("expected failure");
        } catch (IllegalStateException expected) {
            // Expected: callers still see programming errors.
        }

        dispatcher.dispatch(() -> events.add("fresh"));
        assertEquals(Arrays.asList("fresh"), events);
    }
}
