import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * 设备本机 Java 进程:直连 GUIAgent 抽象 socket @guiagent,跑 whohuatv 搜片 5 步序列。
 * 验证"设备本机进程 AF_UNIX 直连"路径(等价 run-search.py,载体从 TCP 改为 LocalSocket)。
 *
 * 编译: javac -encoding UTF-8 -cp <android.jar> -d out G.java
 * 打 dex: java -cp <d8.jar> com.android.tools.r8.D8 --min-api 28 --output classes.dex out/G.class
 * 推送: adb push classes.dex /data/local/tmp/
 * 运行: adb shell "CLASSPATH=/data/local/tmp/classes.dex app_process / G 庆余年"
 */
public class G {
    static LocalSocket sock;

    /** 发一行 JSON+\n, 读至第一个 \n。 */
    static String send(String json) throws Exception {
        OutputStream o = sock.getOutputStream();
        o.write((json + "\n").getBytes("UTF-8"));
        o.flush();
        InputStream in = sock.getInputStream();
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        int c;
        while ((c = in.read()) != -1) {
            if (c == '\n') break;
            b.write(c);
        }
        return b.toString("UTF-8");
    }

    static void msleep(long ms) throws Exception { Thread.sleep(ms); }

    public static void main(String[] args) throws Exception {
        String kw = (args.length > 0) ? args[0] : "庆余年";
        sock = new LocalSocket();
        sock.connect(new LocalSocketAddress("@guiagent", LocalSocketAddress.Namespace.ABSTRACT));

        System.out.println("[1] start -> " + send(
            "{\"id\":\"1\",\"op\":\"start\",\"args\":{\"pkg\":\"com.wohuatv.launcher\"}}"));
        msleep(1500);

        System.out.println("[2] click entry -> " + send(
            "{\"id\":\"2\",\"op\":\"click_node\",\"args\":{\"id\":\"classsic_nav_search\"}}"));
        msleep(1000);

        String r3 = send("{\"id\":\"3\",\"op\":\"set_text\",\"args\":{\"id\":\"mid_search_text_et\",\"text\":\"" + kw + "\"}}");
        System.out.println("[3] set_text -> " + r3);
        if (r3.contains("\"ok\":false") || r3.contains("SET_TEXT_FAILED")) {
            System.out.println("[3b] fallback -> " + send(
                "{\"id\":\"3b\",\"op\":\"set_text_fallback\",\"args\":{\"id\":\"mid_search_text_et\",\"text\":\"" + kw + "\"}}"));
        }
        msleep(500);

        System.out.println("[4] click search -> " + send(
            "{\"id\":\"4\",\"op\":\"click_node\",\"args\":{\"id\":\"mid_search_text\"}}"));
        msleep(1800);

        System.out.println("[5] find results -> " + send(
            "{\"id\":\"5\",\"op\":\"find\",\"args\":{\"id\":\"pop_mid_content_item_tv\",\"limit\":20}}"));
        sock.close();
    }
}
