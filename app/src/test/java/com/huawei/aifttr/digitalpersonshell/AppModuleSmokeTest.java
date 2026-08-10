package com.huawei.aifttr.digitalpersonshell;

import org.junit.Test;

/**
 * 模块骨架冒烟测试（T-001）：验证 :app 模块构建与 JVM 单测可用（含 mockito）。
 */
public class AppModuleSmokeTest {

    @Test
    public void smokeTest_mockitoAvailable() {
        java.util.List<String> mockedList = org.mockito.Mockito.mock(java.util.List.class);
        org.mockito.Mockito.when(mockedList.size()).thenReturn(1);
        org.junit.Assert.assertEquals(1, mockedList.size());
    }
}
