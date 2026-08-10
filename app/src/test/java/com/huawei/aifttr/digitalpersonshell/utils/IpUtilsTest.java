package com.huawei.aifttr.digitalpersonshell.utils;

import org.junit.Test;

import android.content.Context;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;

import java.util.Optional;

/**
 * IpUtils 测试（T-WS-02 / S-WS-01/02）。
 */
public class IpUtilsTest {

    @Test
    public void setLastSegmentToOne_normalIp_lastSegmentIsOne() {
        assertEquals("192.168.1.1", IpUtils.setLastSegmentToOne("192.168.1.25"));
    }

    @Test
    public void setLastSegmentToOne_alreadyOne_staysOne() {
        assertEquals("10.0.0.1", IpUtils.setLastSegmentToOne("10.0.0.1"));
    }

    @Test
    public void setLastSegmentToOne_invalidSegmentCount_throwsIllegalArg() {
        assertThrows(IllegalArgumentException.class, () -> IpUtils.setLastSegmentToOne("1.2.3"));
    }

    @Test
    public void setLastSegmentToOne_outOfRangeSegment_throwsIllegalArg() {
        assertThrows(IllegalArgumentException.class, () -> IpUtils.setLastSegmentToOne("1.2.3.999"));
    }

    @Test
    public void setLastSegmentToOne_null_throwsIllegalArg() {
        assertThrows(IllegalArgumentException.class, () -> IpUtils.setLastSegmentToOne(null));
    }

    @Test
    public void setLastSegmentToOne_empty_throwsIllegalArg() {
        assertThrows(IllegalArgumentException.class, () -> IpUtils.setLastSegmentToOne(""));
    }

    @Test
    public void isInvalidIp_nullOrEmpty_returnsTrue() {
        assertEquals(true, IpUtils.isInvalidIp(null));
        assertEquals(true, IpUtils.isInvalidIp(""));
        assertEquals(true, IpUtils.isInvalidIp("not-an-ip"));
    }

    @Test
    public void isInvalidIp_valid_returnsFalse() {
        assertEquals(false, IpUtils.isInvalidIp("192.168.1.1"));
    }

    /** 无 ConnectivityManager（mock Context 默认 systemService 返回 null）→ Optional.empty。 */
    @Test
    public void getActiveNetworkIpAddress_noConnectivityManager_returnsEmpty() {
        Context context = org.mockito.Mockito.mock(Context.class);
        Optional<String> ip = IpUtils.getActiveNetworkIpAddress(context);
        assertEquals(false, ip.isPresent());
    }
}
