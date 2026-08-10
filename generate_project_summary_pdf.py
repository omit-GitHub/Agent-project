#!/usr/bin/env python3
"""Generate a PDF summary of the GUIAPP project using fpdf2."""

import os
from fpdf import FPDF

# ─────────────────────────────────────────────────────────────
# Find a CJK font
# ─────────────────────────────────────────────────────────────
def find_cjk_font():
    """Find a TTF font that supports Chinese characters."""
    candidates = [
        # Windows
        "C:/Windows/Fonts/msyh.ttc",      # Microsoft YaHei
        "C:/Windows/Fonts/simhei.ttf",     # SimHei
        "C:/Windows/Fonts/simsun.ttc",     # SimSun
        "C:/Windows/Fonts/msyhbd.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class ProjectPDF(FPDF):
    def __init__(self, font_path):
        super().__init__()
        self.font_path = font_path
        self.set_auto_page_break(auto=True, margin=20)

        # Register CJK font (regular)
        self.add_font("CJK", "", font_path, uni=True)
        # Try to find bold variant
        bold_candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",
            font_path,  # fallback to regular
        ]
        bold_path = None
        for bp in bold_candidates:
            if os.path.exists(bp):
                bold_path = bp
                break
        self.add_font("CJK", "B", bold_path, uni=True)

    def header(self):
        if self.page_no() > 1:
            self.set_font("CJK", "", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, "GUIAPP 项目结构总览", align="L")
            self.cell(0, 8, f"第 {self.page_no()} 页", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200, 200, 220)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("CJK", "", 7)
        self.set_text_color(170, 170, 170)
        self.cell(0, 10, "Generated: 2026-08-10 | GUIAgent · DigitalPersonShell", align="C")

    def add_cover(self):
        self.add_page()
        # Title block with background
        self.set_fill_color(240, 242, 255)
        self.rect(0, 0, self.w, 90, "F")

        self.set_y(20)
        self.set_font("CJK", "B", 26)
        self.set_text_color(30, 30, 120)
        self.cell(0, 16, "GUIAPP 项目结构总览", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_font("CJK", "", 13)
        self.set_text_color(100, 100, 140)
        self.cell(0, 10, "Project Structure Summary", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("CJK", "", 10)
        self.set_text_color(120, 120, 140)
        self.cell(0, 7, "华为 FTTR 中屏盒 · GUIAgent 智能语音交互系统", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, "目标设备: 华为 AZ102u-10 (RK3566, Android 9, armeabi-v7a)", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.cell(0, 7, "生成日期: 2026-08-10", align="C", new_x="LMARGIN", new_y="NEXT")

        # Divider line
        self.set_y(92)
        self.set_draw_color(60, 80, 180)
        self.set_line_width(1)
        self.line(20, 92, self.w - 20, 92)
        self.set_line_width(0.2)

        # Quick stats box
        self.set_y(100)
        self.set_font("CJK", "B", 12)
        self.set_text_color(40, 40, 40)
        self.cell(0, 10, "项目概览", new_x="LMARGIN", new_y="NEXT")
        self.set_font("CJK", "", 10)
        self.set_text_color(60, 60, 60)

        stats = [
            ("包名", "com.huawei.aifttr.digitalpersonshell"),
            ("版本", "0.1.0 (versionCode 1)"),
            ("Java 源文件", "116 个（主代码）+ 29 个（测试）"),
            ("Python 脚本", "16 个（辅助控制脚本）"),
            ("代码总行数", "~15,700 行 Java"),
            ("原生库 (.so)", "16 个 (armeabi-v7a, DUI-lite SDK)"),
            ("声学模型 (.bin)", "11 个 (SSPE/VAD/唤醒)"),
            ("APK 大小", "~35 MB"),
        ]
        for key, val in stats:
            self.set_font("CJK", "B", 10)
            self.set_text_color(50, 50, 80)
            self.cell(35, 7, key + ":")
            self.set_font("CJK", "", 10)
            self.set_text_color(60, 60, 60)
            self.cell(0, 7, val, new_x="LMARGIN", new_y="NEXT")

    def section_title(self, num, title):
        self.ln(6)
        # Accent bar
        y = self.get_y()
        self.set_fill_color(60, 80, 180)
        self.rect(self.l_margin, y, 3, 10, "F")
        self.set_x(self.l_margin + 7)
        self.set_font("CJK", "B", 15)
        self.set_text_color(30, 30, 100)
        self.cell(0, 10, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 185, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def sub_title(self, text):
        self.ln(3)
        self.set_font("CJK", "B", 12)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("CJK", "", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text, indent=8):
        x = self.l_margin + indent
        self.set_x(x)
        self.set_font("CJK", "", 10)
        self.set_text_color(60, 80, 160)
        self.cell(5, 6, "•")
        self.set_text_color(50, 50, 50)
        w = self.w - self.r_margin - x - 5
        self.multi_cell(w, 6, text)
        self.ln(0.5)

    def kv_line(self, key, value, indent=8):
        x = self.l_margin + indent
        self.set_x(x)
        self.set_font("CJK", "B", 10)
        self.set_text_color(40, 40, 70)
        self.cell(self.get_string_width(key + ": ") + 2, 6, key + ": ")
        self.set_font("CJK", "", 10)
        self.set_text_color(60, 60, 60)
        w = self.w - self.r_margin - self.get_x()
        self.multi_cell(w, 6, value)
        self.ln(0.5)

    def add_table(self, headers, rows, col_widths=None):
        usable = self.w - self.l_margin - self.r_margin
        if col_widths is None:
            col_widths = [usable / len(headers)] * len(headers)
        else:
            total = sum(col_widths)
            col_widths = [w / total * usable for w in col_widths]

        # Header
        self.set_font("CJK", "B", 9)
        self.set_fill_color(230, 233, 248)
        self.set_text_color(30, 30, 100)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, " " + h, border=1, fill=True)
        self.ln()

        # Rows
        self.set_font("CJK", "", 9)
        self.set_text_color(50, 50, 50)
        fill = False
        for row in rows:
            if self.get_y() > self.h - 25:
                self.add_page()
                # Re-draw header
                self.set_font("CJK", "B", 9)
                self.set_fill_color(230, 233, 248)
                self.set_text_color(30, 30, 100)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 8, " " + h, border=1, fill=True)
                self.ln()
                self.set_font("CJK", "", 9)
                self.set_text_color(50, 50, 50)
                fill = False

            if fill:
                self.set_fill_color(248, 248, 255)
            else:
                self.set_fill_color(255, 255, 255)

            max_lines = 1
            for i, cell_text in enumerate(row):
                text_w = self.get_string_width(cell_text)
                lines = max(1, int(text_w / (col_widths[i] - 2)) + 1)
                max_lines = max(max_lines, lines)

            row_h = max(7, max_lines * 6)

            x_start = self.get_x()
            y_start = self.get_y()

            for i, cell_text in enumerate(row):
                x = x_start + sum(col_widths[:i])
                self.set_xy(x, y_start)
                # cell background
                self.rect(x, y_start, col_widths[i], row_h, "DF" if fill else "D")
                self.set_xy(x + 1, y_start + 1)
                self.multi_cell(col_widths[i] - 2, 6, cell_text)

            self.set_xy(x_start, y_start + row_h)
            fill = not fill
        self.ln(3)

    def dir_tree(self, lines):
        """Draw a directory tree with monospace-like formatting."""
        self.set_font("CJK", "", 8.5)
        for text, is_dir, depth in lines:
            if self.get_y() > self.h - 22:
                self.add_page()
            indent = self.l_margin + depth * 4
            self.set_x(indent)
            if is_dir:
                self.set_text_color(30, 30, 120)
            else:
                self.set_text_color(80, 80, 80)
            self.cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)


def build_pdf():
    font_path = find_cjk_font()
    if not font_path:
        print("ERROR: No CJK font found. Cannot generate PDF with Chinese text.")
        return

    print(f"Using font: {font_path}")
    pdf = ProjectPDF(font_path)

    # ═══ COVER PAGE ═══
    pdf.add_cover()

    # ═══ 1. 项目概述 ═══
    pdf.add_page()
    pdf.section_title("1", "项目概述")
    pdf.body_text(
        "GUIAPP 是一个面向华为 AZ102u-10 FTTR 中屏盒（RK3566 芯片，Android 9，armeabi-v7a）"
        "的 Android 应用项目，集成了两大核心能力模块："
    )
    pdf.bullet(
        "GUIAgent — 基于无障碍服务（AccessibilityService）的 GUI 自动化控制框架。"
        "通过 HTTP/WebSocket 接口接收远程指令，操控爱奇艺、腾讯视频、夸克浏览器等第三方 APP。"
    )
    pdf.bullet(
        "DigitalPersonShell — 语音交互引擎编排层，集成唤醒（Wakeup）、语音活动检测（VAD）、"
        "语音识别（ASR）、语音合成（TTS）四大引擎，实现语音唤醒 → 对话 → 语音控制全流程。"
    )
    pdf.body_text(
        "项目使用 Java 11 开发，Gradle 9.0 + AGP 8.7 构建。包名 com.huawei.aifttr.digitalpersonshell，"
        "APK 约 35MB（含 DUI-lite SDK 的 16 个 .so 原生库 + 11 个声学模型）。"
        "应用无 launcher 图标，通过 adb shell am start 显式启动 LaunchActivity。"
    )

    # ═══ 2. 技术栈 ═══
    pdf.section_title("2", "技术栈")
    pdf.add_table(
        ["类别", "详情"],
        [
            ["语言", "Java 11（主语言）+ Python 3（辅助脚本）"],
            ["构建", "Gradle 9.0 + Android Gradle Plugin 8.7.0"],
            ["目标平台", "Android 9+ (minSdk 28, targetSdk/compileSdk 35)"],
            ["ABI", "armeabi-v7a（与 DUI-lite 原生库一致）"],
            ["HTTP 服务", "原生 ServerSocket（端口 8765，零外部依赖）"],
            ["WebSocket", "原生 ServerSocket（端口 8322，手动 HTTP Upgrade）"],
            ["JSON", "Gson 2.10.1"],
            ["网络", "OkHttp 4.12.0 + okhttp-sse（云端 ASR/TTS/授权）"],
            ["语音 SDK", "DUI-lite SDK 3.17.0（思必驰）+ 16 个 .so"],
            ["测试", "JUnit 4.13.2 + Mockito 4.11.0"],
            ["UI", "AndroidX AppCompat 1.7.1 + Material 1.12.0"],
        ],
        [3, 7],
    )

    # ═══ 3. 目录结构 ═══
    pdf.section_title("3", "项目目录结构")
    pdf.body_text("以下为项目核心目录树（已省略 build/、.gradle/ 等构建产物）：")

    tree = [
        ("GUIAPP/", True, 0),
        ("├── app/", True, 0),
        ("│   ├── build.gradle.kts", False, 1),
        ("│   ├── keystore/aispeechbox_1.jks   (签名密钥)", False, 1),
        ("│   └── src/", True, 1),
        ("│       ├── libs/DUI-lite-SDK-3.17.0.jar", False, 2),
        ("│       ├── main/", True, 2),
        ("│       │   ├── aidl/com/stb/stbcmd/   (STB AIDL 接口)", True, 3),
        ("│       │   ├── assets/   (11 个声学模型 .bin)", True, 3),
        ("│       │   ├── java/", True, 3),
        ("│       │   │   ├── com/guiagent/executor/   (GUIAgent 模块)", True, 4),
        ("│       │   │   │   ├── commands/common/   (8 个通用命令)", True, 5),
        ("│       │   │   │   ├── commands/aiqiyi/   (Python 脚本)", True, 5),
        ("│       │   │   │   ├── commands/aiqiyi_java/   (16 个 Java 命令)", True, 5),
        ("│       │   │   │   ├── commands/tencent_java/   (15 个 Java 命令)", True, 5),
        ("│       │   │   │   ├── commands/quark_java/   (9 个 Java 命令)", True, 5),
        ("│       │   │   │   ├── GuiAgentService.java   (无障碍服务主类)", False, 5),
        ("│       │   │   │   ├── HttpCompoundServer.java   (HTTP API)", False, 5),
        ("│       │   │   │   ├── WsCommandServer.java   (WebSocket)", False, 5),
        ("│       │   │   │   ├── CompoundRegistry.java   (命令注册表)", False, 5),
        ("│       │   │   │   └── ...", False, 5),
        ("│       │   │   └── com/huawei/aifttr/digitalpersonshell/   (语音模块)", True, 4),
        ("│       │   │       ├── VoiceApplication.java   (Application 入口)", False, 5),
        ("│       │   │       ├── sdk/   (DUI-lite 桥接层)", True, 5),
        ("│       │   │       ├── services/   (4 引擎编排 + WebSocket 对话)", True, 5),
        ("│       │   │       ├── ui/   (LaunchActivity + 悬浮气泡)", True, 5),
        ("│       │   │       └── utils/   (日志 + 工具类)", True, 5),
        ("│       │   ├── jniLibs/armeabi-v7a/   (16 个 .so 原生库)", True, 3),
        ("│       │   └── res/   (布局/颜色/字符串/XML 配置)", True, 3),
        ("│       └── test/   (29 个单元测试文件)", True, 2),
        ("├── build.gradle.kts   (根构建脚本)", False, 0),
        ("├── settings.gradle.kts", False, 0),
        ("├── README.md   (编译部署手册)", False, 0),
        ("└── http_service_guide.md   (HTTP API 文档 v3.0)", False, 0),
    ]
    pdf.dir_tree(tree)

    # ═══ 4. 核心模块 ═══
    pdf.section_title("4", "核心模块详解")

    # 4.1 GUIAgent
    pdf.sub_title("4.1 GUIAgent — GUI 自动化控制")
    pdf.body_text(
        "位于 com.guiagent.executor 包。核心架构围绕 Android AccessibilityService 构建，"
        "在系统「设置→无障碍」开启后常驻运行，自动启动 HTTP + WebSocket 服务接收远程指令。"
    )

    pdf.bullet("GuiAgentService — 无障碍服务主类（继承 AccessibilityService），全局控制中枢。启动 HTTP(:8765) + WebSocket(:8322) 服务，将指令翻译为无障碍手势/按键操作。")
    pdf.bullet("HttpCompoundServer — HTTP 复合命令服务器，提供 POST /v1/compound 和 GET /v1/health 两个端点，原生 ServerSocket 零外部依赖。")
    pdf.bullet("WsCommandServer — WebSocket 原子操作服务器，支持手动 HTTP Upgrade 握手，适用于逐帧实时交互。")
    pdf.bullet("CompoundRegistry — 命令注册表，管理复合命令的注册与路由分发。")
    pdf.bullet("DpadAdapter — 遥控器按键适配器，通过 STB AIDL 接口控制机顶盒方向键。")
    pdf.bullet("StateCapture / StateProvider — 屏幕状态采集，获取前台 App 包名 + UI 节点树摘要。")
    pdf.bullet("Nodes / Match / Protocol — UI 节点匹配层，遍历无障碍节点树进行文本/ID 匹配。")

    pdf.sub_title("4.1.1 命令体系 (commands/)")
    pdf.body_text("命令分为通用命令和 APP 专属命令两层：")
    pdf.add_table(
        ["目录", "说明", "内容"],
        [
            ["common/", "通用命令（8 个）", "GoBack, GoHome, Search, Play, VolumeUp/Down/Mute, GetState"],
            ["aiqiyi/", "爱奇艺 Python", "播放/选集/倍速/清晰度/亮度（7 个 .py 脚本）"],
            ["aiqiyi_java/", "爱奇艺 Java", "16 个 Java Command 类（完整 Java 重写版）"],
            ["tencent_java/", "腾讯视频 Java", "15 个 Java Command 类（播放/选集/倍速/亮度等）"],
            ["quark_java/", "夸克浏览器 Java", "9 个 Java Command 类（搜索/文件浏览/导航等）"],
        ],
        [2.5, 3, 4.5],
    )

    # 4.2 DigitalPersonShell
    pdf.sub_title("4.2 DigitalPersonShell — 语音交互引擎")
    pdf.body_text(
        "位于 com.huawei.aifttr.digitalpersonshell 包，编排 4 大语音引擎，实现端到端语音对话："
    )
    pdf.add_table(
        ["类名", "角色", "说明"],
        [
            ["VoiceApplication", "Application 入口", "启动时装配 SpeechProvider + VoiceServiceManager"],
            ["SpeechProvider", "DUI SDK 桥接", "封装思驰 DUI-lite SDK，统一语音能力接口"],
            ["VoiceServiceManager", "4 引擎编排", "管理 ASR/VAD/Wakeup/TTS 生命周期与数据流"],
            ["LocalWakeupEngine", "本地唤醒", "加载 wakeup .bin 模型，离线语音唤醒"],
            ["LocalVadEngine", "本地 VAD", "加载 vad .bin 模型，语音端点检测"],
            ["CloudASREngine", "云端 ASR", "OkHttp WebSocket 实时语音转文字"],
            ["CloudTTSEngine", "云端 TTS", "OkHttp 连接云端文字转语音"],
            ["VoiceGateway", "对话状态机", "IDLE→WAKEUP→LISTENING→THINKING→SPEAKING"],
            ["ChatBubbleController", "悬浮气泡 UI", "SYSTEM_ALERT_WINDOW 展示对话状态"],
        ],
        [3.5, 2.5, 4],
    )

    pdf.sub_title("4.3 原生资源")
    pdf.body_text("JNI 原生库（jniLibs/armeabi-v7a/，共 16 个 .so）：")
    so_text = (
        "libsspe.so, libvad.so, libwakeup.so, libasr.so, libasrpp.so, libliteca.so, "
        "libduiutils.so, libgram.so, libngram.so, libmds.so, libmp3.so, libopusogg.so, "
        "libsemantic_dui.so, libsemantic_navi.so, libspeex.so, libailog2.so"
    )
    pdf.bullet(so_text)

    pdf.ln(2)
    pdf.body_text(
        "声学模型（assets/，共 11 个 .bin）：包含 SSPE 回声消除模型（多种麦克风阵列配置：2mic/4mic/6mic）、"
        "VAD 端点检测模型（v0.11/v0.12）、唤醒词模型（\"小翼管家\" / 通用唤醒词）等。"
    )

    # ═══ 5. 通信接口 ═══
    pdf.section_title("5", "通信接口")

    pdf.sub_title("5.1 HTTP 复合命令接口（端口 8765）")
    pdf.body_text("设备与应用同局域网时可直连（无需 USB/adb），提供两个端点：")
    pdf.bullet("POST /v1/compound — 执行复合命令。JSON body: {\"command\": \"aiqiyi.select_episode\", \"params\": [3]}")
    pdf.bullet("GET /v1/health — 健康检查，返回状态 + 可用命令列表")
    pdf.body_text("命令串行执行（同一时刻只处理一条），默认超时 15 秒。错误码包括 UNKNOWN_COMMAND、BAD_PARAMS、NO_MATCH、TIMEOUT 等 8 种。")

    pdf.sub_title("5.2 WebSocket 原子操作接口（端口 8322）")
    pdf.body_text("提供更底层的逐帧交互控制，支持手动 HTTP Upgrade 握手，适用于需要实时双向通信的场景。")

    pdf.sub_title("5.3 AIDL 接口（STB 机顶盒控制）")
    pdf.body_text("通过 IStbCmdService / IStbCmdCallback AIDL 接口与机顶盒系统服务通信，实现遥控器方向键模拟（DpadAdapter）。")

    # ═══ 6. 支持的 APP ═══
    pdf.section_title("6", "支持的第三方 APP")
    pdf.add_table(
        ["APP", "命令数", "功能覆盖"],
        [
            ["爱奇艺", "16 Java + 7 Python", "播放/暂停、选集、倍速、清晰度、亮度、详情页"],
            ["腾讯视频", "15 Java", "播放/暂停、选集、倍速、清晰度、亮度"],
            ["夸克浏览器", "9 Java", "搜索、文件浏览、页面导航、滚动"],
            ["系统通用", "8 个通用命令", "返回、主页、搜索、播放、音量控制、状态查询"],
        ],
        [2.5, 3, 4.5],
    )
    pdf.body_text("推荐调用顺序: launcher_search → play → 播放控制 → 选集。命令假设 APP 已在正确的前台页面。")

    # ═══ 7. 测试体系 ═══
    pdf.section_title("7", "测试体系")
    pdf.body_text("共 29 个单元测试文件，使用 JUnit 4 + Mockito，纯 JVM 运行（Mock 隔离 SDK）：")
    pdf.add_table(
        ["模块", "测试类", "覆盖范围"],
        [
            ["aiqiyi_java", "AiQiyiCommandTest 等", "命令注册 + 播放切换逻辑"],
            ["common", "CommonCommandTest 等", "PlayCommand + 搜索结果解析"],
            ["quark", "QuarkCommandRegistrationTest 等", "命令注册 + 搜索结果"],
            ["tencent", "TencentCommandTest", "腾讯视频命令测试"],
            ["CompoundRegistry", "CompoundRegistryTest 等", "注册/路由/集成测试"],
            ["HttpCompoundServer", "HttpCompoundServerTest", "请求解析 + 响应格式"],
            ["VoiceServiceManager", "AppModuleSmokeTest 等", "引擎初始化 + 状态机"],
            ["WakeupEngine", "WakeupEngineHelperTest", "配置加载"],
            ["数据模型", "VoiceSessionTest 等", "ChatRequest/VoiceSession 验证"],
        ],
        [3, 4, 3],
    )

    # ═══ 8. 构建与部署 ═══
    pdf.section_title("8", "构建与部署")
    pdf.body_text("目标设备: 华为 AZ102u-10 FTTR 中屏盒（RK3566, Android 9, DHCP 动态 IP，重启后 IP 末段会变）")
    pdf.bullet("编译: JDK 17 + Android SDK + Gradle 9.0.0（本地 binary，不用 ./gradlew）")
    pdf.bullet("产出: app/build/outputs/apk/debug/app-debug.apk（约 35MB）")
    pdf.bullet("签名: keystore/aispeechbox_1.jks（V1 + V2 签名，debug/release 同一密钥）")
    pdf.bullet("安装: adb connect <IP>:5555 → uninstall → install → am start 启动")
    pdf.bullet("前置: 需在「设置→无障碍」开启 GuiAgentService（HTTP Server 才会启动）")
    pdf.bullet("特点: 应用无 launcher 图标，通过 adb shell am start 显式启动 LaunchActivity")
    pdf.bullet("注意: 网段可能有多台设备，需通过端口扫描（nc -z :5555）+ 用户确认末段定位中屏")

    # ═══ 9. 项目统计 ═══
    pdf.section_title("9", "项目统计摘要")
    pdf.add_table(
        ["指标", "数值"],
        [
            ["Java 源文件（main）", "116 个"],
            ["Python 脚本（main）", "16 个"],
            ["单元测试文件", "29 个"],
            ["Java 代码总行数", "~15,700 行"],
            ["JNI 原生库 (.so)", "16 个（armeabi-v7a）"],
            ["声学模型 (.bin)", "11 个"],
            ["AIDL 接口", "2 个（IStbCmdService + Callback）"],
            ["HTTP 端点", "2 个（/v1/compound, /v1/health）"],
            ["WebSocket 端口", "1 个（:8322）"],
            ["支持 APP 数", "3 个（爱奇艺/腾讯/夸克）+ 通用命令"],
            ["复合命令总数", "~48 个（含通用 + 各 APP 专属）"],
            ["签名密钥", "aispeechbox_1.jks"],
            ["文档", "README.md + http_service_guide.md (v3.0)"],
        ],
        [4, 6],
    )

    # ═══ Output ═══
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "GUIAPP_项目结构总览.pdf")
    pdf.output(output_path)
    print(f"PDF written to: {output_path}")
    print(f"Pages: {pdf.page_no()}")
    return output_path


if __name__ == "__main__":
    build_pdf()
