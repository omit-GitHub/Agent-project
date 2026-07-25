/*
 * guiagent-search.c — 设备本机 C 进程,直连 GUIAgent 抽象 socket 验证搜片。
 *
 * 连 AF_UNIX abstract "\0@guiagent",连发 run-search.py 的 5 步指令序列,
 * 打印每步原始 NDJSON 响应。用法:
 *   ./guiagent-search [关键词]    (默认 庆余年)
 *
 * 前置: GUIAgent 无障碍服务已开,且当前进程在设备本机(AF_UNIX 直连,不经 adb)。
 * 编译(NDK): aarch64-linux-android28-clang -o guiagent-search guiagent-search.c
 *            armv7a-linux-androideabi28-clang -o guiagent-search guiagent-search.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/un.h>

/* 连抽象 socket @guiagent。名字字面量 "@guiagent"(含 @),sun_path[0]='\0' 标记抽象。 */
static int connect_guiagent(void) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) { perror("socket"); return -1; }
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    addr.sun_path[0] = '\0';
    const char *name = "@guiagent";
    size_t nlen = strlen(name);
    memcpy(&addr.sun_path[1], name, nlen);
    socklen_t len = (socklen_t)(sizeof(sa_family_t) + 1 + nlen);  /* 抽象名无需 null 结尾 */
    if (connect(fd, (struct sockaddr *)&addr, len) < 0) {
        perror("connect @guiagent");
        close(fd);
        return -1;
    }
    return fd;
}

/* 发一行 JSON+\n, 读至第一个 \n。返回响应长度,-1 失败。buf 以 \0 结尾。 */
static int send_recv(int fd, const char *json, char *buf, int bufsz) {
    char line[4096];
    int n = snprintf(line, sizeof(line), "%s\n", json);
    if (n < 0 || n >= (int)sizeof(line)) { fprintf(stderr, "line too long\n"); return -1; }
    if (write(fd, line, (size_t)n) != n) { perror("write"); return -1; }
    int total = 0;
    while (total < bufsz - 1) {
        ssize_t r = read(fd, buf + total, (size_t)(bufsz - 1 - total));
        if (r <= 0) break;
        total += (int)r;
        buf[total] = '\0';
        if (strchr(buf, '\n')) break;
    }
    char *nl = strchr(buf, '\n');
    if (nl) *nl = '\0';
    return total;
}

static void msleep(int ms) {
    struct timespec ts = { ms / 1000, (long)(ms % 1000) * 1000000L };
    nanosleep(&ts, NULL);
}

int main(int argc, char **argv) {
    const char *kw = (argc > 1) ? argv[1] : "庆余年";
    int fd = connect_guiagent();
    if (fd < 0) return 1;
    char buf[16384];
    char j[1024];

    /* 1. 拉起 whohuatv launcher */
    send_recv(fd, "{\"id\":\"1\",\"op\":\"start\",\"args\":{\"pkg\":\"com.wohuatv.launcher\"}}", buf, sizeof(buf));
    printf("[1] start -> %s\n", buf);
    msleep(1500);

    /* 2. 点搜索入口 */
    send_recv(fd, "{\"id\":\"2\",\"op\":\"click_node\",\"args\":{\"id\":\"classsic_nav_search\"}}", buf, sizeof(buf));
    printf("[2] click entry -> %s\n", buf);
    msleep(1000);

    /* 3. 填关键词(优先 set_text;失败降级 set_text_fallback) */
    snprintf(j, sizeof(j),
        "{\"id\":\"3\",\"op\":\"set_text\",\"args\":{\"id\":\"mid_search_text_et\",\"text\":\"%s\"}}", kw);
    send_recv(fd, j, buf, sizeof(buf));
    printf("[3] set_text -> %s\n", buf);
    if (strstr(buf, "\"ok\":false") || strstr(buf, "SET_TEXT_FAILED")) {
        snprintf(j, sizeof(j),
            "{\"id\":\"3b\",\"op\":\"set_text_fallback\",\"args\":{\"id\":\"mid_search_text_et\",\"text\":\"%s\"}}", kw);
        send_recv(fd, j, buf, sizeof(buf));
        printf("[3b] fallback -> %s\n", buf);
    }
    msleep(500);

    /* 4. 触发搜索 */
    send_recv(fd, "{\"id\":\"4\",\"op\":\"click_node\",\"args\":{\"id\":\"mid_search_text\"}}", buf, sizeof(buf));
    printf("[4] click search -> %s\n", buf);
    msleep(1800);

    /* 5. 读片源结果 */
    send_recv(fd, "{\"id\":\"5\",\"op\":\"find\",\"args\":{\"id\":\"pop_mid_content_item_tv\",\"limit\":20}}",
              buf, sizeof(buf));
    printf("[5] find results -> %s\n", buf);

    close(fd);
    return 0;
}
