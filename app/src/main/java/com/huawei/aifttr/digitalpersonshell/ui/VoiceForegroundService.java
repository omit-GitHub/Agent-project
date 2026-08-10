package com.huawei.aifttr.digitalpersonshell.ui;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;

import com.huawei.aifttr.digitalpersonshell.VoiceApplication;
import com.huawei.aifttr.digitalpersonshell.data.model.session.VoiceSession;
import com.huawei.aifttr.digitalpersonshell.services.OkHttpWebSocketFactory;
import com.huawei.aifttr.digitalpersonshell.services.VoiceGateway;
import com.huawei.aifttr.digitalpersonshell.services.WebSocketChatService;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IpSupplier;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.IVoiceService;
import com.huawei.aifttr.digitalpersonshell.services.interfaces.WebSocketFactory;
import com.huawei.aifttr.digitalpersonshell.ui.bubble.ChatBubbleController;
import com.huawei.aifttr.digitalpersonshell.ui.bubble.ChatBubblePresenter;
import com.huawei.aifttr.digitalpersonshell.utils.IpUtils;
import com.huawei.aifttr.digitalpersonshell.utils.log.Logger;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;

/**
 * 唤醒常驻前台 Service（T-008 / M-09 / SC-012 / NFR-004）。
 * <p>
 * 无 UI 场景下作为唤醒引擎常驻载体，onStartCommand 初始化 VoiceGateway
 * 并置前台通知，维持 {@link VoiceSession} 为 Listening。
 */
public class VoiceForegroundService extends Service {

    private static final String TAG = VoiceForegroundService.class.getSimpleName();
    private static final String CHANNEL_ID = "voice_foreground";
    private static final int NOTIFICATION_ID = 1001;

    private VoiceGateway gateway;
    private VoiceSession session;
    private IVoiceService voiceService;
    private WebSocketChatService chatService;
    /** 对话气泡 overlay 控制器（T-B05 装配，onDestroy 释放）。 */
    private ChatBubbleController bubbleController;

    /**
     * 真机装配阶段注入 IVoiceService（T-004/集成）。
     */
    public void setVoiceService(IVoiceService voiceService) {
        this.voiceService = voiceService;
    }

    /**
     * 注入预构造的 VoiceGateway（测试/装配用）。
     */
    public void setGateway(VoiceGateway gateway) {
        this.gateway = gateway;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Logger.info(TAG, "[VOICE] 前台服务 onStartCommand，初始化语音链路");
        initVoice();
        // 真机置前台通知保活；JVM 单测下 Notification.Builder 抛异常，吞掉以保持状态可测
        try {
            startForeground(NOTIFICATION_ID, buildNotification());
            Logger.info(TAG, "[VOICE] 前台通知已置，唤醒常驻保活");
        } catch (Exception e) {
            Logger.error(TAG, "[VOICE] startForeground 失败（真机路径不应至此）", e);
        }
        return START_STICKY;
    }

    private void initVoice() {
        if (session == null) {
            session = new VoiceSession();
        }
        // 未注入时从 Application 装配点取（真机路径）；JVM 单测取 null，gateway 不建
        if (voiceService == null) {
            voiceService = VoiceApplication.getVoiceService();
        }
        Logger.info(TAG, "[VOICE] initVoice: voiceService=" + (voiceService != null)
                + " gateway=" + (gateway != null));
        session.onInitSuccess();
        if (gateway == null && voiceService != null) {
            gateway = new VoiceGateway(voiceService, session);
            // 装配 WebSocket 对话服务：gateway 作 ChatCallback，setChatService 打破循环（T-WS-07）
            IpSupplier ipSupplier = () -> IpUtils.getActiveNetworkIpAddress(getApplication());
            WebSocketFactory factory = new OkHttpWebSocketFactory();
            ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
            chatService = new WebSocketChatService(ipSupplier, factory, scheduler, gateway);
            gateway.setChatService(chatService);
            // 装配对话气泡 UI：Controller（框架侧）+ Presenter（逻辑侧），注册 BubbleUiCallback（T-B05）
            // JVM 单测下 WindowManager 为 stub，构造包 try-catch（与 startForeground 同模式）
            try {
                bubbleController = new ChatBubbleController(this);
                ChatBubblePresenter bubblePresenter = new ChatBubblePresenter(bubbleController);
                gateway.setBubbleCallback(bubblePresenter);
                Logger.info(TAG, "[VOICE] 对话气泡 Controller+Presenter 已装配");
            } catch (Exception e) {
                Logger.error(TAG, "[VOICE] 气泡装配失败（真机路径不应至此）", e);
            }
            Logger.info(TAG, "[VOICE] VoiceGateway + WebSocketChatService 已创建，监听唤醒/ASR/TTS/对话");
        } else if (voiceService == null) {
            Logger.error(TAG, "[VOICE] voiceService 为 null（VoiceApplication 未装配成功），无法建 Gateway");
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "语音唤醒", NotificationManager.IMPORTANCE_LOW);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification() {
        return new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("语音唤醒运行中")
                .setContentText("正在监听唤醒词")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .build();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        Logger.info(TAG, "[VOICE] 前台服务 onDestroy，释放对话服务");
        if (gateway != null) {
            gateway.release();
            gateway = null;
        }
        if (bubbleController != null) {
            bubbleController.release();
            bubbleController = null;
        }
        if (chatService != null) {
            chatService.release();
            chatService = null;
        }
        super.onDestroy();
    }

    public VoiceSession getSession() {
        return session;
    }
}
