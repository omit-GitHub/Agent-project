package com.huawei.aifttr.digitalpersonshell.utils.log;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 日志过滤类：敏感信息脱敏 + 单条日志长度截断。
 * <p>
 * 移植自 DigitalPerson 日志实现。取代旧 LogMaskUtil。
 */
public final class LogFilter {
    /**
     * 需要过滤的敏感信息字段
     */
    private static final Set<String> FILTER_SET;

    /**
     * 缓存所有字符串对应的待替换pattern，key:匹配的字符串；value:对应的pattern
     */
    private static final Map<String, List<Pattern>> FILTER_PATTERN_MAP;

    /**
     * 访客wifi二维码信: WIFI:...;P:PASSWORD;...
     */
    private static final Pattern WIFI_QR_PASSWORD_PATTERN = Pattern.compile("(WIFI:.*;P:)([^;]+)");

    /**
     * 所有需要过滤的敏感信息模式
     */
    private static final String[] FILTER_REGEX_LIST = new String[]{"(\\bfilterstr\\b[\"]?[=:])\'?([^,&]*)?\'?",
        "(<[^</]*?filterstr>)([^<]*)",
        "(Bearer|Basic|Token)\\s+([A-Za-z0-9+/=._-]+)",
        "(filterstr)=([^&\\s]+)",
        "(filterstr)(为|是)([^\\s，。；：,]+)"};

    static {
        // 初始化敏感信息过滤集合
        Set<String> filterSet = new HashSet<>();
        // 帐号相关
        Collections.addAll(filterSet, "account", "Account", "PPPoEAccount", "familyAccount", "tyAccount", "woAccount",
            "userAccount", "registerAccount", "accountID");
        // 密码相关
        Collections.addAll(filterSet, "pword", "certPassword", "Password", "oldpassword", "newpasswordkey",
            "renewpasswordkey", "oldPassword", "newPassword", "reNewPassword", "psw", "repsw", "pwd", "repwd",
            "password", "passWord", "curPassword", "PassWD", "passwordValid", "useDefaultPassword", "userPassword",
            "pass", "密码");
        // name相关
        Collections.addAll(filterSet, "username", "userName", "Username", "UserName", "nickname", "nickName", "name",
            "User-Name", "familyName", "fileName", "realName", "currentFileName", "名称");
        // 手机号相关
        Collections.addAll(filterSet, "receivePhone", "phone", "Phones");
        // token和client相关
        Collections.addAll(filterSet, "returnToken", "token", "Token", "AcessToken", "accessToken", "mainProfileToken",
            "access_token", "client_id", "clientId", "client_secret");
        // mac相关
        Collections.addAll(filterSet, "MAC", "mac", "srcName", "dstName", "srcMac", "destMac", "apMac", "DeviceMAC",
            "oldMAC", "newMAC", "attachMAC", "MACAttachList");
        // email相关
        Collections.addAll(filterSet, "E-mail", "E-MAIL", "emailAddr", "email", "return_Parameter", "Parameter");
        // 用户相关
        Collections.addAll(filterSet, "user", "User", "USER", "userid", "userId", "userID", "deviceId");
        // 地址相关
        Collections.addAll(filterSet, "deviceAddress", "subMediaAddress", "mainMediaAddress", "ptzAddress",
            "deviceMediaAddress", "address", "originPath", "path", "item.url is");
        // 其他过滤
        Collections.addAll(filterSet, "appSecret", "secret", "Secret", "price", "contacts",
            "telIMEI", "IMEI", "appIDs", "appID", "questionKey", "answer",
            "deviceMatchIdentity", "rtsp", "photoNum", "bindingParam", "returnClientId",
            "sessionID", "sessionId", "sID", "SID", "sId", "sn", "Sn", "SN", "ssdSn",
            "serialNumber", "ssdaSN", "ssdaSn", "ssdbSN", "ssdbSn",
            "defaultSn", "securityCode", "verifyCode", "ssid", "SSID", "ont", "ip", "IP",
            "wanIPAddr", "lanIPAddr", "psk", "PSK", "IMSI", "MSISDN", "MDN", "MSIS_DN",
            "UDID", "emmc", "eUICC", "UUID");
        FILTER_SET = Collections.unmodifiableSet(filterSet);
    }

    static {
        Map<String, List<Pattern>> map = new HashMap<>(FILTER_SET.size());
        for (final String regex : FILTER_REGEX_LIST) {
            for (final String filter : FILTER_SET) {
                final Pattern pattern = Pattern.compile(regex.replace("filterstr", filter));
                List<Pattern> patterns = map.get(filter);
                if (patterns == null) {
                    patterns = new ArrayList<>();
                    map.put(filter, patterns);
                }
                patterns.add(pattern);
            }
        }
        FILTER_PATTERN_MAP = Collections.unmodifiableMap(map);
    }

    /**
     * 格式化字符串
     *
     * @param msg 消息字符串
     * @return 脱敏后的字符串
     */
    public static String replaceLine(final String msg) {
        if (msg == null) {
            return null;
        }

        // 单条日志超过最大长度时截断
        final String message = msg.length() > LogConfig.SINGLE_LOG_MAX_LEN ? msg.substring(0,
            LogConfig.SINGLE_LOG_MAX_LEN) : msg;
        return filter(message);
    }

    /**
     * 过滤关键信息
     *
     * @param message 日志信息
     * @return 返回脱敏过滤后的日志信息
     */
    private static String filter(final String message) {
        // 将对message中'\'过滤
        String msg = message.replaceAll("\\\\", "");
        for (final String str : FILTER_SET) {
            if (!msg.contains(str)) {
                continue;
            }
            final List<Pattern> patterns = FILTER_PATTERN_MAP.get(str);
            if (patterns != null) {
                for (final Pattern pattern : patterns) {
                    msg = filterStr(msg, pattern);
                }
            }
        }

        // 访客wifi密码脱敏
        msg = WIFI_QR_PASSWORD_PATTERN.matcher(msg).replaceAll("$1********");

        return msg.replaceAll("(\\d{1,3}\\.){3}|([A-Fa-f0-9]{2}){5}", "**********");
    }

    /**
     * 过滤关键信息
     *
     * @param message 日志信息
     * @param pattern 过滤正则
     * @return 过滤后的日志消息
     */
    private static String filterStr(final String message, final Pattern pattern) {
        final Matcher matcher = pattern.matcher(message);
        final StringBuffer sb = new StringBuffer();
        while (matcher.find()) {
            matcher.appendReplacement(sb, "********");
        }
        matcher.appendTail(sb);
        return sb.toString();
    }
}
