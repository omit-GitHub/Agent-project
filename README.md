# GUIAPP 编译部署手册

目标设备：华为 AZ102u-10 FTTR 中屏盒（RK3566，Android 9，armeabi-v7a）。
设备使用 DHCP，**重启后 IP 末段会变**，每次部署前需先扫描定位。

## 一键流程

```bash
cd /Users/dp/Desktop/projects/GUIAPP

# ---------- 1. 编译 ----------
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
ANDROID_HOME=/Users/dp/Library/Android/sdk \
PATH=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home/bin:$PATH \
~/.gradle/wrapper/dists/gradle-9.0.0-bin/d6wjpkvcgsg3oed0qlfss3wgl/gradle-9.0.0/bin/gradle \
  :app:assembleDebug --no-daemon

APK=app/build/outputs/apk/debug/app-debug.apk
PKG=com.huawei.aifttr.digitalpersonshell
ADB=/Users/dp/Library/Android/sdk/platform-tools/adb

# ---------- 2. 扫描定位设备（IP 末段每次可能变） ----------
# ping 扫段填充 ARP 表，再找开了 adb 端口 5555 的主机
for i in $(seq 1 254); do ping -c 1 -W 200 192.168.100.$i > /dev/null 2>&1 & done; wait
for h in $(arp -a | grep -o '192\.168\.100\.[0-9]*' | sort -u); do
  nc -z -G 1 $h 5555 2>/dev/null && echo "发现 adb 设备: $h"
done
# 网段上可能有多台屏（如 .195），中屏选哪台看下面说明，确认后填末段：
IP=192.168.100.46

# ---------- 3. 连接 ----------
$ADB kill-server && $ADB start-server
$ADB connect $IP:5555
$ADB -s $IP:5555 get-state   # 应输出 device

# ---------- 4. 删除旧版本 ----------
$ADB -s $IP:5555 uninstall $PKG

# ---------- 5. 安装新版本 ----------
$ADB -s $IP:5555 install "$APK"

# ---------- 6. 启动 ----------
$ADB -s $IP:5555 shell am start -n $PKG/.ui.LaunchActivity

# ---------- 7. 验证 ----------
$ADB -s $IP:5555 shell pidof $PKG   # 输出 PID 即运行中
```

## 分步说明

### 1. 编译

本机无 Android Studio，使用最小依赖编译（JDK 17 + Android SDK + Gradle 9.0.0，均已装好，见 `note.md`）。**不要用 `./gradlew`**（wrapper 会重新下载发行版），直接用上面命令中的本地 Gradle binary。

产出：`app/build/outputs/apk/debug/app-debug.apk`（约 35MB，含 DUI .so + 模型）。

### 2. 扫描定位设备

设备 DHCP 租约不固定（历史上见过 .45 / .46），每次部署前先扫描定位。流程：

1. 对 `192.168.100.0/24` 做一次 ping 扫描，填充本机 ARP 表；
2. 对 ARP 表里的主机逐个 `nc -z <ip> 5555`，开了 5555 的就是 adb 设备。

注意：

- 网段上可能同时有多台屏（例如 .195 也开 5555，是另一台），**中屏要靠用户指定的末段确认**，别装错设备。
- 不要依赖 MAC 地址识别：note.md 里记过 `00:e0:4c:99:75:fb`（当时 .45），但实测 .46 的 MAC 是 `00:e0:4c:df:9b:a7`，以端口扫描 + 用户确认的末段为准。
- Mac 本机也在该网段（`192.168.100.28`）。若一个 5555 都扫不到，确认设备已开机、与 Mac 同网段，再重扫一次。

### 3. 连接

`get-state` 必须返回 `device`。若返回 `offline`，按顺序执行 `adb kill-server && adb start-server` 后重新 `connect`（这是已知的本机 adb server transport 状态问题，无需 USB / root）。

### 4. 删除旧版本

```bash
$ADB -s $IP:5555 uninstall com.huawei.aifttr.digitalpersonshell
```

会清掉应用数据。如果想保留数据做覆盖安装，跳过第 4 步，第 5 步改用：

```bash
$ADB -s $IP:5555 install -r -d "$APK"
```

### 5-6. 安装并启动

应用无 launcher 图标，必须显式 start 组件：

```bash
$ADB -s $IP:5555 shell am start -n com.huawei.aifttr.digitalpersonshell/.ui.LaunchActivity
```

### 7. 验证

`pidof` 输出一个 PID 即表示进程已起来。如需看日志：

```bash
$ADB -s $IP:5555 logcat | grep digitalpersonshell
```

## 排错速查

| 症状 | 处理 |
|---|---|
| 扫描不到任何 5555 端口 | 设备未开机/不在同网段；确认后重跑 ping 扫描 |
| 扫出多台设备，不知哪台是中屏 | 以用户指定的末段为准，不要凭 MAC 猜 |
| `adb connect` 后 `get-state` 为 `offline` | `adb kill-server && adb start-server` 后重新 connect |
| `install` 报 `INSTALL_FAILED_VERSION_DOWNGRADE` | 先执行第 4 步卸载，或加 `-d` 参数 |
| 编译要重新下载 Gradle/依赖 | 检查是否误用了 `./gradlew`；改用 README 中的本地 binary 路径 |
