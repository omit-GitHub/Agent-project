package com.guiagent.executor;

import com.guiagent.executor.commands.common.*;
import com.guiagent.executor.commands.aiqiyi.*;
import com.guiagent.executor.commands.tencent.*;

import org.junit.Before;
import org.junit.Test;

import java.util.List;

import static org.junit.Assert.*;

/**
 * 验证所有命令正确注册到 CompoundRegistry。
 */
public class CompoundRegistryIntegrationTest {

    private CompoundRegistry registry;

    @Before
    public void setUp() {
        registry = new CompoundRegistry();
        // 模拟 GuiAgentService.registerAllCommands()
        // 通用命令
        registry.register(new GoBackCommand());
        registry.register(new GoHomeCommand());
        registry.register(new VolumeUpCommand());
        registry.register(new VolumeDownCommand());
        registry.register(new VolumeMuteCommand());
        // 爱奇艺
        registry.register(new AiQiyiTogglePlayCommand());
        registry.register(new AiQiyiNextEpisodeCommand());
        registry.register(new AiQiyiPrevEpisodeCommand());
        registry.register(new AiQiyiToggleControlBarCommand());
        registry.register(new AiQiyiOpenEpisodePanelCommand());
        registry.register(new AiQiyiCloseEpisodePanelCommand());
        registry.register(new AiQiyiScrollEpisodeUpCommand());
        registry.register(new AiQiyiScrollEpisodeDownCommand());
        registry.register(new AiQiyiSelectEpisodeCommand());
        registry.register(new AiQiyiSetSpeedCommand());
        registry.register(new AiQiyiSetQualityCommand());
        registry.register(new AiQiyiBrightnessUpCommand());
        registry.register(new AiQiyiBrightnessDownCommand());
        registry.register(new AiQiyiOpenDetailCommand());
        registry.register(new AiQiyiCloseDetailCommand());
        // 腾讯
        registry.register(new TencentTogglePlayCommand());
        registry.register(new TencentNextEpisodeCommand());
        registry.register(new TencentPrevEpisodeCommand());
        registry.register(new TencentToggleControlBarCommand());
        registry.register(new TencentOpenEpisodePanelCommand());
        registry.register(new TencentCloseEpisodePanelCommand());
        registry.register(new TencentScrollEpisodeUpCommand());
        registry.register(new TencentScrollEpisodeDownCommand());
        registry.register(new TencentSelectEpisodeCommand());
        registry.register(new TencentSetSpeedCommand());
        registry.register(new TencentSetQualityCommand());
        registry.register(new TencentBrightnessUpCommand());
        registry.register(new TencentBrightnessDownCommand());
        registry.register(new TencentOpenDetailCommand());
    }

    @Test
    public void testAllCommandsRegistered_countIs34() {
        List<String> commands = registry.listCommands();
        assertEquals("Should have 34 commands registered", 34, commands.size());
    }

    @Test
    public void testCommonCommands_present() {
        List<String> commands = registry.listCommands();
        assertTrue(commands.contains("go_back"));
        assertTrue(commands.contains("go_home"));
        assertTrue(commands.contains("volume_up"));
        assertTrue(commands.contains("volume_down"));
        assertTrue(commands.contains("volume_mute"));
    }

    @Test
    public void testAiQiyiCommands_present() {
        List<String> commands = registry.listCommands();
        assertTrue(commands.contains("aiqiyi.toggle_play"));
        assertTrue(commands.contains("aiqiyi.next_episode"));
        assertTrue(commands.contains("aiqiyi.select_episode"));
        assertTrue(commands.contains("aiqiyi.set_speed"));
        assertTrue(commands.contains("aiqiyi.set_quality"));
        assertTrue(commands.contains("aiqiyi.brightness_up"));
        assertTrue(commands.contains("aiqiyi.brightness_down"));
    }

    @Test
    public void testTencentCommands_present() {
        List<String> commands = registry.listCommands();
        assertTrue(commands.contains("tencent.toggle_play"));
        assertTrue(commands.contains("tencent.next_episode"));
        assertTrue(commands.contains("tencent.select_episode"));
        assertTrue(commands.contains("tencent.set_speed"));
        assertTrue(commands.contains("tencent.set_quality"));
        assertTrue(commands.contains("tencent.brightness_up"));
        assertTrue(commands.contains("tencent.brightness_down"));
    }
}
