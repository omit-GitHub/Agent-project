package com.huawei.aifttr.digitalpersonshell.utils.log;

/**
 * 日志模块配置（单例）。
 * <p>
 * 移植自 DigitalPerson 日志实现。使用前需设置 logPath 与 logFileName。
 */
public class LogConfig {
    /**
     * 文件大小限制
     */
    public static final long FILE_SIZE_LIMIT = 20971520L;

    static final int SINGLE_LOG_MAX_LEN = 1024;

    private static final String TAG = LogConfig.class.getSimpleName();

    private static final int MAX_NUM_OF_LOG_FILE = 20;

    private String mLogFileName;

    private String mLogPath;

    // 日志文件的最大个数
    private int mMaxLogFileNum = MAX_NUM_OF_LOG_FILE;

    private LogConfig() {
    }

    /**
     * 私有静态内部类
     */
    private static class SingletonInstance {
        private static final LogConfig INSTANCE = new LogConfig();
    }

    /**
     * 获取LogConfig实例
     *
     * @return LogConfig实例
     */
    public static LogConfig getInstance() {
        return SingletonInstance.INSTANCE;
    }

    /**
     * 设置日志文件的最大个数
     *
     * @param num 日志文件的最大个数
     */
    public void setMaxLogFileNum(int num) {
        this.mMaxLogFileNum = num;
    }

    /**
     * 获取log目录路径
     *
     * @return log目录路径
     */
    public String getLogPath() {
        return mLogPath;
    }

    /**
     * 设置log路径
     *
     * @param path path
     * @return 返回对象实例
     */
    public LogConfig setLogPath(final String path) {
        mLogPath = path;
        return this;
    }

    /**
     * 设置日志名称
     *
     * @param logFileName 日志名称
     */
    public void setLogFileName(String logFileName) {
        mLogFileName = logFileName;
    }

    /**
     * 获取日志名称
     *
     * @return 日志名称
     */
    public String getLogFileName() {
        return mLogFileName;
    }

    /**
     * 获取日志文件的最大个数
     *
     * @return 日志文件的最大个数
     */
    public int getMaxLogFileNum() {
        return mMaxLogFileNum;
    }
}
