package com.huawei.aifttr.digitalpersonshell.services.interfaces;

import java.util.Optional;

/**
 * IP 提供者端口（T-WS-04）。
 * <p>
 * 抽象「取本机活动网络 IPv4」，便于单测注入固定 IP，避免 Android Context 依赖。
 * 生产实现 {@code () -> IpUtils.getActiveNetworkIpAddress(context)}。
 */
@FunctionalInterface
public interface IpSupplier {

    /**
     * @return 当前活动网络 IPv4；无则 empty
     */
    Optional<String> get();
}
