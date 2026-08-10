package com.huawei.aifttr.digitalpersonshell.utils.log;

import static com.huawei.aifttr.digitalpersonshell.utils.log.LogFilter.replaceLine;

import android.util.Log;

import java.io.File;
import java.io.IOException;
import java.io.Writer;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;

/**
 * 核心日志类：Logcat 输出 + 本地文件落盘（带轮转、脱敏、安全校验）。
 * <p>
 * 移植自 DigitalPerson 日志实现，拍平 ILogger 代理层后直用。
 * {@link #isDebugMode} 控制 debug/verbose 是否打 Logcat；
 * {@link #shouldSaveLogToLocalStorage}（默认 true）控制本地落盘。
 * 落盘前必须经 {@link LogConfig#getInstance()} 配置 logPath / logFileName。
 */
public final class Logger {
    /**
     * 是否输出日志到控制台，debug 版本输出，release 版本不输出。
     */
    public static boolean isDebugMode;

    private static final String TAG = Logger.class.getSimpleName();

    private static final String DEBUG_TAG = "Debug";

    private static final String INFO_TAG = "Notice";

    private static final String WARN_TAG = "Critical";

    private static final String ERROR_TAG = "Error";

    // 回车:ASCII码13
    private static final int RETURN_ASCII_CODE = 13;

    // 换行:ASCII码10
    private static final int NEW_LINE_ASCII_CODE = 10;

    // 是否输出日志到本地文件
    private static boolean shouldSaveLogToLocalStorage = true;

    // 本地日志文件
    private static File sLogFile;

    private Logger() {
        // empty method
    }

    public static void setShouldSaveLogToLocalStorage(final boolean isRecordFlag) {
        shouldSaveLogToLocalStorage = isRecordFlag;
    }

    /**
     * 日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     */
    public static void verbose(final String tag, final String msg) {
        verbose(tag, msg, null);
    }

    /**
     * 日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     * @param e   异常
     */
    public static void verbose(final String tag, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s %s", msg, e.getMessage());
        }
        if (isDebugMode) {
            Log.v(tag, replaceLine(format));
        }
        writeToLocalStorage(TAG, getMsg(tag, replaceLine(format)));
    }

    /**
     * debug日志
     *
     * @param tag 日志tag
     * @param msg 日志msg
     */
    public static void debug(final String tag, final String msg) {
        debug(tag, msg, null);
    }

    /**
     * debug日志
     *
     * @param tag 日志tag
     * @param msg 日志msg
     * @param e   异常
     */
    public static void debug(final String tag, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s %s", msg, e.getMessage());
        }
        if (isDebugMode) {
            Log.v(tag, replaceLine(format));
        }
        writeToLocalStorage(DEBUG_TAG, getMsg(tag, replaceLine(format)));
    }

    /**
     * 提示日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     */
    public static void info(final String tag, final String msg) {
        info(tag, msg, (Throwable) null);
    }

    /**
     * 提示日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     * @param e   异常
     */
    public static void info(final String tag, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s: %s", msg, e.getMessage());
        }
        Log.i(tag, replaceLine(format));
        writeToLocalStorage(INFO_TAG, getMsg(tag, replaceLine(format)));
    }

    /**
     * 提示日志打印（带TrackId）
     *
     * @param tag     日志tag
     * @param trackId 链路追踪ID
     * @param msg     日志信息
     */
    public static void info(final String tag, final String trackId, final String msg) {
        info(tag, trackId, msg, null);
    }

    /**
     * 提示日志打印（带TrackId）
     *
     * @param tag     日志tag
     * @param trackId 链路追踪ID
     * @param msg     日志信息
     * @param e       异常
     */
    public static void info(final String tag, final String trackId, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s: %s", msg, e.getMessage());
        }
        Log.i(tag, replaceLine(format));
        writeToLocalStorage(INFO_TAG, getMsg(trackId, tag, replaceLine(format)));
    }

    /**
     * 警报日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     */
    public static void warn(final String tag, final String msg) {
        warn(tag, msg, null);
    }

    /**
     * 警报日志打印
     *
     * @param tag 日志tag
     * @param msg 日志信息
     * @param e   异常
     */
    public static void warn(final String tag, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s: %s", msg, e.getMessage());
        }
        Log.w(tag, replaceLine(format));
        writeToLocalStorage(WARN_TAG, getMsg(tag, replaceLine(format)));
    }

    /**
     * error日志
     *
     * @param tag 日志tag
     * @param msg 日志msg
     */
    public static void error(final String tag, final String msg) {
        error(tag, msg, (Throwable) null);
    }

    /**
     * error日志
     *
     * @param tag 日志tag
     * @param msg 日志msg
     * @param e   异常
     */
    public static void error(final String tag, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s: %s", msg, e.getMessage());
        }
        Log.e(tag, replaceLine(format));
        writeToLocalStorage(ERROR_TAG, getMsg(tag, replaceLine(format)));
    }

    /**
     * error日志（带TrackId）
     *
     * @param tag     日志tag
     * @param trackId 链路追踪ID
     * @param msg     日志msg
     */
    public static void error(final String tag, final String trackId, final String msg) {
        error(tag, trackId, msg, null);
    }

    /**
     * error日志（带TrackId）
     *
     * @param tag     日志tag
     * @param trackId 链路追踪ID
     * @param msg     日志msg
     * @param e       异常
     */
    public static void error(final String tag, final String trackId, final String msg, Throwable e) {
        String format;
        if (e == null) {
            format = msg;
        } else {
            format = String.format("%s: %s", msg, e.getMessage());
        }
        Log.e(tag, replaceLine(format));
        writeToLocalStorage(ERROR_TAG, getMsg(trackId, tag, replaceLine(format)));
    }

    private static synchronized void writeToLocalStorage(final String logType, final String msg) {
        if (!shouldSaveLogToLocalStorage) {
            return;
        }
        if (LogConfig.getInstance().getLogPath() == null) {
            return;
        }
        final SimpleDateFormat simpleDateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.ENGLISH);
        final String dateStr = simpleDateFormat.format(new Date());
        final String outputStr = String.format(Locale.ENGLISH, "[%s][%s]-- %s", dateStr, logType, msg);
        if (!isLogFileAvailable()) {
            return;
        }

        // 文件超大，删除最老文件，并创建新文件
        final File logDir = new File(LogConfig.getInstance().getLogPath());
        if (FileUtil.isFileOversize(sLogFile, LogConfig.FILE_SIZE_LIMIT)) {
            final File parentFile = sLogFile.getParentFile();
            if (parentFile == null) {
                return;
            }
            final File[] files = parentFile.listFiles();
            final int fileCount = files != null ? files.length : 0;
            if (fileCount > 0) {
                // 根据最后修改时间进行排序
                Arrays.sort(files, (file1, file2) -> (int) (file2.lastModified() - file1.lastModified()));

                // 文件个数超大
                for (int i = fileCount; i >= LogConfig.getInstance().getMaxLogFileNum(); i--) {
                    File fileToDelete = files[i - 1];
                    // 两层校验：拒绝符号链接 + 拒绝路径穿越
                    if (fileToDelete.isFile()
                            && !FileUtil.isSymlink(fileToDelete)
                            && FileUtil.isFileInDir(fileToDelete, logDir)
                            && !fileToDelete.delete()) {
                        return;
                    }
                }
                sLogFile = new File(LogConfig.getInstance().getLogPath(), LogConfig.getInstance().getLogFileName()
                    + "_" + System.currentTimeMillis() + ".log");
            }
        }

        // 写入前两层校验：拒绝符号链接 + 拒绝路径穿越
        if (FileUtil.isSymlink(sLogFile) || !FileUtil.isFileInDir(sLogFile, logDir)) {
            Log.e(TAG, "Log file symlink or path escape detected, skip write");
            return;
        }
        boolean isAppend = sLogFile.exists() && (sLogFile.length() <= LogConfig.FILE_SIZE_LIMIT);
        try (Writer fileWriter = FileUtil.getBufferedWriter(sLogFile.getCanonicalPath(), isAppend)) {
            fileWriter.write(outputStr);
            fileWriter.write(RETURN_ASCII_CODE);
            fileWriter.write(NEW_LINE_ASCII_CODE);
            fileWriter.flush();
        } catch (IOException e) {
            Log.e(TAG, "Write log IOException");
        }
    }

    private static boolean isLogFileAvailable() {
        final File logFolder = new File(LogConfig.getInstance().getLogPath());
        File lastModifiedFile = FileUtil.getLastModifiedFileUnderDir(logFolder);
        if (lastModifiedFile != null) {
            sLogFile = lastModifiedFile;
        } else {
            sLogFile = new File(LogConfig.getInstance().getLogPath(),
                LogConfig.getInstance().getLogFileName() + "_" + System.currentTimeMillis() + ".log");
        }

        // 两层校验：拒绝符号链接 + 拒绝路径穿越
        if (FileUtil.isSymlink(sLogFile) || !FileUtil.isFileInDir(sLogFile, logFolder)) {
            Log.e(TAG, "Log file is symlink or path escape, create new one");
            sLogFile = new File(LogConfig.getInstance().getLogPath(),
                LogConfig.getInstance().getLogFileName() + "_" + System.currentTimeMillis() + ".log");
        }

        try {
            // 日志文件不存在则创建
            if (!FileUtil.isFileExist(sLogFile)) {
                return sLogFile.createNewFile();
            }
        } catch (IOException exception) {
            Log.e(TAG, "Create log file failed");
            return false;
        }
        return true;
    }

    /**
     * 日志记录格式
     *
     * @param tag 日志tag
     * @param msg 日志信息
     * @return 日志记录格式
     */
    private static String getMsg(final String tag, final String msg) {
        return String.format(Locale.ENGLISH, "[ %1$s ]::%2$s", tag, msg);
    }

    /**
     * 日志记录格式（带TrackId）
     *
     * @param trackId 链路追踪ID
     * @param tag     日志tag
     * @param msg     日志信息
     * @return 日志记录格式，trackId为空时降级为原格式
     */
    private static String getMsg(final String trackId, final String tag, final String msg) {
        if (trackId == null || trackId.isEmpty()) {
            return String.format(Locale.ENGLISH, "[ %1$s ]::%2$s", tag, msg);
        }
        return String.format(Locale.ENGLISH, "[%1$s][%2$s]::%3$s", trackId, tag, msg);
    }
}
