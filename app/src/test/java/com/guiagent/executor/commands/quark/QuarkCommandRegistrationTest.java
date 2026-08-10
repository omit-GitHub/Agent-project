package com.guiagent.executor.commands.quark;

import static org.junit.Assert.assertEquals;

import com.guiagent.executor.CompoundCommand;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class QuarkCommandRegistrationTest {

    @Test
    public void commandNames_matchHttpApi() {
        List<CompoundCommand> commands = Arrays.asList(
                new QuarkLaunchAppCommand(),
                new QuarkClickNavigationCommand(),
                new QuarkScrollUpCommand(),
                new QuarkScrollDownCommand(),
                new QuarkSelectFileCommand(),
                new QuarkGoBackCommand(),
                new QuarkSearchCommand());

        assertEquals(Arrays.asList(
                        "quark.launch_app",
                        "quark.click_navigation",
                        "quark.scroll_up",
                        "quark.scroll_down",
                        "quark.select_file",
                        "quark.go_back",
                        "quark.search"),
                commands.stream().map(CompoundCommand::getName).collect(Collectors.toList()));
    }
}
