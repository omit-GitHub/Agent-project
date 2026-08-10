package com.guiagent.executor.commands.quark;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonObject;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class QuarkSearchResultTest {

    @Test
    public void initialsCanMatchAChineseFileName() {
        AccessibilityNodeInfo item = node(
                null, null, 100, 200, 500, 320,
                node("夸克网盘能干什么.mp4", null, 0, 0, 0, 0));
        AccessibilityNodeInfo root = node(
                null, null, 0, 0, 0, 0,
                node("kkwp", null, 0, 0, 0, 0), item);

        JsonObject data = QuarkSearchResult.build("KKWP", root, Collections.singletonList(item));

        assertEquals("found", data.get("search_status").getAsString());
        assertEquals(1, data.get("count").getAsInt());
        assertEquals("夸克网盘能干什么.mp4",
                data.getAsJsonArray("items").get(0).getAsJsonObject().get("text").getAsString());
    }

    @Test
    public void echoedQueryWithoutFilesIsNotFound() {
        AccessibilityNodeInfo root = node(
                null, null, 0, 0, 0, 0,
                node("ZXQVB", null, 0, 0, 0, 0));

        JsonObject data = QuarkSearchResult.build("zxqvb", root, Collections.emptyList());

        assertEquals("not_found", data.get("search_status").getAsString());
        assertEquals(0, data.get("count").getAsInt());
    }

    @Test
    public void inputNotAppliedIsUnknownEvenWhenOldFilesRemain() {
        AccessibilityNodeInfo oldItem = node("旧文件.mp4", null, 100, 200, 500, 320);
        AccessibilityNodeInfo root = node(
                null, null, 0, 0, 0, 0,
                node("K", null, 0, 0, 0, 0), oldItem);

        JsonObject data = QuarkSearchResult.build(
                "KKWP", root, Collections.singletonList(oldItem));

        assertEquals("unknown", data.get("search_status").getAsString());
        assertEquals(1, data.get("count").getAsInt());
    }

    @Test
    public void recyclerViewItemsReuseSelectionOrdering() {
        AccessibilityNodeInfo first = node("第一项.mp4", null, 100, 100, 300, 220);
        AccessibilityNodeInfo second = node("第二项.mp4", null, 400, 100, 600, 220);
        AccessibilityNodeInfo third = node("第三项.mp4", null, 100, 300, 300, 420);
        AccessibilityNodeInfo recyclerView = node(
                null,
                "androidx.recyclerview.widget.RecyclerView",
                0,
                0,
                0,
                0,
                third,
                second,
                first);
        AccessibilityNodeInfo root = node(null, null, 0, 0, 0, 0, recyclerView);

        List<AccessibilityNodeInfo> items = QuarkFileItems.find(root);

        assertEquals(Arrays.asList(first, second, third), items);
    }

    private static AccessibilityNodeInfo node(
            String text,
            String className,
            int left,
            int top,
            int right,
            int bottom,
            AccessibilityNodeInfo... children) {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        when(node.getText()).thenReturn(text);
        when(node.getClassName()).thenReturn(className);
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
