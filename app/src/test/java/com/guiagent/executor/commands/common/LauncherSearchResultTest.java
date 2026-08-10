package com.guiagent.executor.commands.common;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;

public class LauncherSearchResultTest {

    @Test
    public void foundResultsAreIndexedInRowMajorOrder() {
        AccessibilityNodeInfo first = node("第一项", 100, 400, 280, 440);
        AccessibilityNodeInfo second = node("第二项", 320, 402, 500, 442);
        AccessibilityNodeInfo third = node("第三项", 100, 700, 280, 740);

        JsonObject data = SearchCommand.buildSearchData(
                "测试", Arrays.asList(third, second, first), null);

        assertEquals("测试", data.get("query").getAsString());
        assertEquals("found", data.get("search_status").getAsString());
        assertEquals(3, data.get("count").getAsInt());
        JsonArray items = data.getAsJsonArray("items");
        assertEquals(1, items.get(0).getAsJsonObject().get("index").getAsInt());
        assertEquals("第一项", items.get(0).getAsJsonObject().get("text").getAsString());
        assertEquals("第二项", items.get(1).getAsJsonObject().get("text").getAsString());
        assertEquals("第三项", items.get(2).getAsJsonObject().get("text").getAsString());
    }

    @Test
    public void queryInSearchBoxDoesNotBecomeAResult() {
        AccessibilityNodeInfo root = node(
                null,
                0,
                0,
                0,
                0,
                node("谍影重重六", 0, 0, 0, 0),
                node("没有搜索到相关内容", 0, 0, 0, 0));

        JsonObject data = SearchCommand.buildSearchData(
                "谍影重重六", Collections.emptyList(), root);

        assertEquals("not_found", data.get("search_status").getAsString());
        assertEquals(0, data.get("count").getAsInt());
        assertEquals(0, data.getAsJsonArray("items").size());
    }

    @Test
    public void incompleteSearchPageIsUnknown() {
        AccessibilityNodeInfo root = node(null, 0, 0, 0, 0, node("异常页面", 0, 0, 0, 0));

        JsonObject data = SearchCommand.buildSearchData(
                "测试", Collections.emptyList(), root);

        assertEquals("unknown", data.get("search_status").getAsString());
        assertEquals(0, data.get("count").getAsInt());
    }

    private static AccessibilityNodeInfo node(
            String text,
            int left,
            int top,
            int right,
            int bottom,
            AccessibilityNodeInfo... children) {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        when(node.getText()).thenReturn(text);
        when(node.getChildCount()).thenReturn(children.length);
        for (int i = 0; i < children.length; i++) {
            when(node.getChild(i)).thenReturn(children[i]);
        }
        doAnswer(invocation -> {
            Rect bounds = invocation.getArgument(0);
            bounds.left = left;
            bounds.top = top;
            bounds.right = right;
            bounds.bottom = bottom;
            return null;
        }).when(node).getBoundsInScreen(org.mockito.ArgumentMatchers.any(Rect.class));
        return node;
    }
}
