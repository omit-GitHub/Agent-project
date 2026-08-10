package com.guiagent.executor.commands.common;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

import com.google.gson.JsonObject;
import com.guiagent.executor.GuiAgentService;
import com.guiagent.executor.Match;

import org.junit.Test;
import org.mockito.ArgumentCaptor;

import java.util.Arrays;
import java.util.List;

public class PlayCommandTest {

    @Test
    public void indexAndRowColumnSelectTheSamePoster() throws Exception {
        Selection byIndex = execute(params("index", 4));
        Selection byRowColumn = execute(rowColParams(2, 2));

        assertEquals(byIndex.x, byRowColumn.x);
        assertEquals(byIndex.y, byRowColumn.y);
        assertEquals(4, byIndex.data.get("index").getAsInt());
        assertEquals(4, byRowColumn.data.get("index").getAsInt());
        assertEquals(2, byRowColumn.data.get("row").getAsInt());
        assertEquals(2, byRowColumn.data.get("col").getAsInt());
    }

    @Test
    public void firstAndLastIndexesSpanRows() throws Exception {
        Selection first = execute(params("index", 1));
        Selection last = execute(params("index", 4));

        assertEquals(200, first.x);
        assertEquals(250, first.y);
        assertEquals(500, last.x);
        assertEquals(650, last.y);
    }

    @Test
    public void invalidAndOutOfRangeParametersHaveExplicitErrors() throws Exception {
        PlayCommand command = new PlayCommand();

        JsonObject invalidIndex = command.execute(mock(GuiAgentService.class), params("index", 0));
        assertFalse(invalidIndex.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", errorCode(invalidIndex));

        JsonObject invalidRow = command.execute(mock(GuiAgentService.class), rowColParams(0, 1));
        assertFalse(invalidRow.get("ok").getAsBoolean());
        assertEquals("BAD_PARAMS", errorCode(invalidRow));

        JsonObject indexOutOfRange = executeRaw(params("index", 5));
        assertEquals("NO_MATCH", errorCode(indexOutOfRange));

        JsonObject rowOutOfRange = executeRaw(rowColParams(3, 1));
        assertEquals("NO_MATCH", errorCode(rowOutOfRange));

        JsonObject colOutOfRange = executeRaw(rowColParams(2, 3));
        assertEquals("NO_MATCH", errorCode(colOutOfRange));
    }

    private static Selection execute(JsonObject params) throws Exception {
        GuiAgentService service = serviceWithGrid();
        JsonObject response = new PlayCommand().execute(service, params);
        assertTrue(response.get("ok").getAsBoolean());

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<float[]>> pointsCaptor = ArgumentCaptor.forClass(List.class);
        org.mockito.Mockito.verify(service).gesture(pointsCaptor.capture(), anyLong());
        float[] point = pointsCaptor.getValue().get(0);
        return new Selection((int) point[0], (int) point[1], response.getAsJsonObject("data"));
    }

    private static JsonObject executeRaw(JsonObject params) throws Exception {
        return new PlayCommand().execute(serviceWithGrid(), params);
    }

    private static GuiAgentService serviceWithGrid() {
        AccessibilityNodeInfo first = node("第一项", 100, 100, 300, 400);
        AccessibilityNodeInfo second = node("第二项", 400, 100, 600, 400);
        AccessibilityNodeInfo third = node("第三项", 100, 500, 300, 800);
        AccessibilityNodeInfo fourth = node("第四项", 400, 500, 600, 800);
        List<AccessibilityNodeInfo> posters = Arrays.asList(fourth, second, third, first);

        AccessibilityNodeInfo firstTitle = node("第一项", 100, 410, 300, 450);
        AccessibilityNodeInfo secondTitle = node("第二项", 400, 410, 600, 450);
        AccessibilityNodeInfo thirdTitle = node("第三项", 100, 810, 300, 850);
        AccessibilityNodeInfo fourthTitle = node("第四项", 400, 810, 600, 850);
        List<AccessibilityNodeInfo> titles = Arrays.asList(fourthTitle, secondTitle, thirdTitle, firstTitle);

        GuiAgentService service = mock(GuiAgentService.class);
        when(service.findNodes(any(Match.class))).thenAnswer(invocation -> {
            Match match = invocation.getArgument(0);
            if (match.id != null && match.id.contains("pop_mid_content_item_pic")) {
                return posters;
            }
            return titles;
        });
        when(service.gesture(any(), anyLong())).thenReturn(true);
        return service;
    }

    private static AccessibilityNodeInfo node(
            String text, int left, int top, int right, int bottom) {
        AccessibilityNodeInfo node = mock(AccessibilityNodeInfo.class);
        when(node.getText()).thenReturn(text);
        doAnswer(invocation -> {
            Rect bounds = invocation.getArgument(0);
            bounds.left = left;
            bounds.top = top;
            bounds.right = right;
            bounds.bottom = bottom;
            return null;
        }).when(node).getBoundsInScreen(any(Rect.class));
        return node;
    }

    private static JsonObject params(String name, int value) {
        JsonObject params = new JsonObject();
        params.addProperty(name, value);
        return params;
    }

    private static JsonObject rowColParams(int row, int col) {
        JsonObject params = new JsonObject();
        params.addProperty("row", row);
        params.addProperty("col", col);
        return params;
    }

    private static String errorCode(JsonObject response) {
        return response.getAsJsonObject("error").get("code").getAsString();
    }

    private static final class Selection {
        private final int x;
        private final int y;
        private final JsonObject data;

        private Selection(int x, int y, JsonObject data) {
            this.x = x;
            this.y = y;
            this.data = data;
        }
    }
}
