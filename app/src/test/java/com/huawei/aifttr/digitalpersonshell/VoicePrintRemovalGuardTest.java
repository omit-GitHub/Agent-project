package com.huawei.aifttr.digitalpersonshell;

import org.junit.Test;

import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

import static org.junit.Assert.assertTrue;

/**
 * 声纹裁剪完整性校验（TC-013 / SC-011 / BR-007/008/009）。
 * <p>
 * 扫描 :voice 与 :app 的源码及 native/模型资源目录，断言无声纹符号与资源：
 * 类名 IVoicePrintEngine / VoicePrintEngine / core.VoicePrintService / VP*Callback，
 * 资源 libvprint.so / vpr_*.bin / asrpp_gender.bin。
 */
public class VoicePrintRemovalGuardTest {

    /** 声纹符号正则（类名/包路径片段）。onVprintCutDataReceived 是 DUI SDK 强制回调，空实现非残留，不列入。 */
    private static final Pattern VOICE_PRINT_SYMBOL = Pattern.compile(
            "IVoicePrintEngine|VoicePrintEngine|VoicePrintService|"
                    + "VPCreateCallback|VPDeleteCallback|VPIdentifyCallback|"
                    + "VoicePrintCallBack|voicePrintEngine|VoicePrintEngineHelper|"
                    + "getVoicePrintEngine|registerVoicePrint|identifyVoicePrint|"
                    + "feedVoicePrintData|deleteVoicePrint|onVoicePrintData|onVoiceData");

    /** 声纹资源文件名正则。 */
    private static final Pattern VOICE_PRINT_RESOURCE = Pattern.compile(
            "libvprint\\.so|vpr_.*\\.bin|asrpp_gender\\.bin|wakeup_.*_vp\\.bin|wakeup_nihaoxiaoguang_vp\\.bin|wakeup_nihaoxiaoguan_vp\\.bin");

    @Test
    public void noVoicePrintSymbolsOrResources() throws IOException {
        // 单元测试工作目录为 :app 模块目录，上溯一层到项目根
        Path root = Paths.get("").toAbsolutePath().getParent();
        List<String> hits = new ArrayList<>();
        // 仅扫描 main 源集与资源（测试代码中以断言形式出现的声纹名字不视作残留）
        scan(root.resolve("voice/src/main"), hits);
        scan(root.resolve("app/src/main"), hits);
        assertTrue("发现声纹残留，必须裁剪: " + hits, hits.isEmpty());
    }

    private void scan(Path root, List<String> hits) throws IOException {
        if (!Files.exists(root)) {
            return;
        }
        Files.walkFileTree(root, new SimpleFileVisitor<Path>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                String name = file.getFileName().toString();
                // 跳过自身守卫测试
                if (name.contains("VoicePrintRemovalGuard")) {
                    return FileVisitResult.CONTINUE;
                }
                if (VOICE_PRINT_RESOURCE.matcher(name).find()) {
                    hits.add("资源: " + root.relativize(file));
                    return FileVisitResult.CONTINUE;
                }
                if (name.endsWith(".java") || name.endsWith(".kt") || name.endsWith(".xml")
                        || name.endsWith(".kts") || name.endsWith(".gradle")) {
                    try {
                        String content = new String(Files.readAllBytes(file), "UTF-8");
                        if (VOICE_PRINT_SYMBOL.matcher(content).find()) {
                            hits.add("符号: " + root.relativize(file));
                        }
                    } catch (IOException e) {
                        // 忽略读取失败
                    }
                }
                return FileVisitResult.CONTINUE;
            }
        });
    }
}
