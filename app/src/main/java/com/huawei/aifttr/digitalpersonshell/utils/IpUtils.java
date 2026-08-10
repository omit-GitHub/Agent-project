package com.huawei.aifttr.digitalpersonshell.utils;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;

import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.util.List;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * IP 地址工具（T-WS-02，移植自参考 DigitalPerson.IpAddressUtils）。
 * <p>
 * 获取当前活动网络 IPv4 地址；将最后网段改为 .1（用于定位智能体所在网关设备）。
 */
public final class IpUtils {

    private static final String TAG = "IpUtils";
    private static final String IP_PATTERN =
            "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$";
    private static final Pattern PATTERN = Pattern.compile(IP_PATTERN);

    private IpUtils() {
    }

    /**
     * 是否非法 IP。
     */
    public static boolean isInvalidIp(String ip) {
        if (ip == null || ip.trim().isEmpty()) {
            return true;
        }
        return !PATTERN.matcher(ip.trim()).matches();
    }

    /**
     * 获取当前活动网络 IPv4。
     *
     * @param context 上下文
     * @return IPv4 字符串；无活动网络/无 IPv4 返回 empty
     */
    public static Optional<String> getActiveNetworkIpAddress(Context context) {
        if (context == null) {
            return Optional.empty();
        }
        ConnectivityManager connManager =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (connManager == null) {
            Logger.warn(TAG, "No ConnectivityManager");
            return Optional.empty();
        }
        Network activeNetwork = connManager.getActiveNetwork();
        if (activeNetwork == null) {
            Logger.warn(TAG, "No active network");
            return Optional.empty();
        }
        LinkProperties linkProperties = connManager.getLinkProperties(activeNetwork);
        if (linkProperties == null) {
            Logger.warn(TAG, "No link properties for active network");
            return Optional.empty();
        }
        List<LinkAddress> linkAddresses = linkProperties.getLinkAddresses();
        for (LinkAddress linkAddress : linkAddresses) {
            InetAddress address = linkAddress.getAddress();
            if (address instanceof Inet4Address
                    && !address.isLoopbackAddress()
                    && !address.isLinkLocalAddress()) {
                String ip = address.getHostAddress();
                Logger.info(TAG, "Active Network IP: " + ip);
                return Optional.of(ip);
            }
        }
        Logger.warn(TAG, "No IPv4 address found for active network");
        return Optional.empty();
    }

    /**
     * 将 IP 最后一段改为 1。
     *
     * @param ipAddress IPv4 地址
     * @return 最后段为 1 的地址
     * @throws IllegalArgumentException 参数为空/非法
     */
    public static String setLastSegmentToOne(String ipAddress) {
        if (ipAddress == null || ipAddress.trim().isEmpty()) {
            throw new IllegalArgumentException("ipAddress is null or empty");
        }
        String[] parts = ipAddress.trim().split("\\.");
        if (parts.length != 4) {
            throw new IllegalArgumentException("invalid ipAddress");
        }
        for (String part : parts) {
            try {
                int num = Integer.parseInt(part);
                if (num < 0 || num > 255) {
                    throw new IllegalArgumentException("IP segment is out of range: " + part);
                }
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException("IP address contains non-numeric characters: " + part);
            }
        }
        return parts[0] + "." + parts[1] + "." + parts[2] + ".1";
    }
}
