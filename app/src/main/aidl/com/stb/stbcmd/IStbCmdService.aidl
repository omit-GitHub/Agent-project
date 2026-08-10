package com.stb.stbcmd;

import com.stb.stbcmd.IStbCmdCallback;

interface IStbCmdService {
    void setLogUpload(String logServerUrl, String ftpServerUrl, int logType, int logLevel, int lastTime, int logTimer);
    void ExecCMD(String command, int waitTime, IStbCmdCallback callback);
    int startTcpDump(String ip, String port, int duration, String uploadUrl, IStbCmdCallback callback);
    void registerCallback(IStbCmdCallback callback);
    void ungregisterCallback();
}
