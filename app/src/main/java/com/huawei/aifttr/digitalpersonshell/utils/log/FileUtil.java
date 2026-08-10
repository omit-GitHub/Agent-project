package com.huawei.aifttr.digitalpersonshell.utils.log;

import java.io.File;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

/**
 * 文件操作相关工具类（含符号链接/路径穿越安全校验）。
 * <p>
 * 移植自 DigitalPerson 日志实现。
 */
public final class FileUtil {
    private static final String TAG = FileUtil.class.getName();

    private FileUtil() {
        // empty method
    }

    /**
     * 验证文件当前大小是否已超过上限
     *
     * @param file      文件
     * @param sizeLimit 文件大小上限
     * @return Return check file result
     */
    public static boolean isFileOversize(final File file, long sizeLimit) {
        if (file == null) {
            return false;
        }
        return file.length() > sizeLimit;
    }

    /**
     * 检测文件是否存在
     *
     * @param file 文件
     * @return 文件是否存在
     */
    public static boolean isFileExist(final File file) {
        if (file == null) {
            return false;
        }
        return file.exists();
    }

    /**
     * 获取目录下最近修改的对象文件对象，没有该目录则创建
     *
     * @param dir 目录文件对象
     * @return 文件对象
     */
    public static File getLastModifiedFileUnderDir(File dir) {
        if (!dir.exists()) {
            final boolean isSuccess = dir.mkdirs();
            Logger.info(TAG, "Create folder: " + isSuccess);
        }

        File[] files = dir.listFiles();
        if (files == null || files.length == 0) {
            return null;
        }

        // 第1层：过滤符号链接；第2层：校验真实路径在目录内
        List<File> validFiles = new ArrayList<>();
        for (File file : files) {
            if (!isSymlink(file) && isFileInDir(file, dir) && file.isFile()) {
                validFiles.add(file);
            }
        }
        if (validFiles.isEmpty()) {
            return null;
        }

        // 根据最后修改时间进行排序
        validFiles.sort((file1, file2) -> Long.compare(file2.lastModified(), file1.lastModified()));
        return validFiles.get(0);
    }

    /**
     * 获取Writer
     *
     * @param url      path
     * @param isAppend 是否追加
     * @return Writer
     * @throws IOException IO异常
     */
    public static Writer getBufferedWriter(String url, boolean isAppend) throws IOException {
        return isAppend
            ? Files.newBufferedWriter(Paths.get(url), Charset.defaultCharset(), StandardOpenOption.APPEND)
            : Files.newBufferedWriter(Paths.get(url));
    }

    /**
     * 基于路径删除目标文件(循环则递归)
     *
     * @param filePath    文件路径
     * @param boundaryDir 路径边界目录，防止符号链接逃逸，为null时不做边界校验
     * @return 文件及其子文件是否已全部删除
     * @throws IOException IO异常
     */
    public static boolean deleteFile(String filePath, File boundaryDir) throws IOException {
        if (filePath == null || filePath.trim().isEmpty()) {
            return false;
        }

        File file = new File(filePath);
        // 路径不存在，直接返回失败
        if (!file.exists()) {
            return false;
        }

        // 第1层：符号链接不跟随，直接删除链接本身
        if (isSymlink(file)) {
            return file.delete();
        }

        // 第2层：路径边界校验
        if (boundaryDir != null && !isFileInDir(file, boundaryDir)) {
            Logger.error(TAG, "deleteFile path escape detected: " + filePath);
            return false;
        }

        // 若是文件，直接删除
        if (file.isFile()) {
            return file.delete();
        }

        // 若是目录，递归删除所有子文件和子目录后，再删除自身
        if (file.isDirectory()) {
            File[] childFiles = file.listFiles();
            if (childFiles == null) {
                return file.delete(); // 空目录直接删除
            }

            // 递归删除所有子文件/子目录
            boolean allDeleted = true;
            for (File child : childFiles) {
                if (isSymlink(child)) {
                    child.delete();
                    continue;
                }
                if (boundaryDir != null && !isFileInDir(child, boundaryDir)) {
                    Logger.error(TAG, "deleteFile child path escape: " + child.getAbsolutePath());
                    continue;
                }
                if (!deleteFile(child.getCanonicalPath(), boundaryDir)) {
                    allDeleted = false;
                }
            }

            // 所有子项删除成功后，删除当前目录
            return allDeleted && file.delete();
        }

        return false;
    }

    /**
     * 判断文件是否为符号链接
     * 真实文件的 absolutePath == canonicalPath，符号链接则不等
     *
     * @param file 文件对象
     * @return true=符号链接 false=真实文件
     */
    public static boolean isSymlink(File file) {
        if (file == null) {
            return true;
        }
        try {
            return !file.getAbsolutePath().equals(file.getCanonicalPath());
        } catch (IOException e) {
            return true;
        }
    }

    /**
     * 校验文件的真实路径是否在指定目录内（防止路径穿越）
     *
     * @param file 待校验文件
     * @param dir  预期目录
     * @return true=合法（真实路径在目录内） false=非法
     */
    public static boolean isFileInDir(File file, File dir) {
        if (file == null || dir == null) {
            return false;
        }
        try {
            String canonicalDir = dir.getCanonicalPath() + File.separator;
            String canonicalFile = file.getCanonicalPath();
            return canonicalFile.startsWith(canonicalDir);
        } catch (IOException e) {
            return false;
        }
    }

    /**
     * 判断文件名是否合法（防止路径穿越）
     *
     * @param baseDir  基础目录（如上传目录）
     * @param fileName 待校验的文件名
     * @return true=合法 false=非法（含路径穿越风险/参数异常）
     */
    public static boolean isFileNameValid(File baseDir, String fileName) {
        // 空值/空字符串校验
        if (baseDir == null || fileName == null || fileName.trim().isEmpty()) {
            return false;
        }

        String trimmedFileName = fileName.trim();
        // 过滤路径穿越敏感字符
        if (trimmedFileName.contains("..") || trimmedFileName.contains("/") || trimmedFileName.contains("\\")) {
            return false;
        }

        try {
            // 获取规范路径，校验前缀（避免路径穿越）
            String canonicalBaseDir = baseDir.getCanonicalPath();
            File targetFile = new File(baseDir, trimmedFileName);
            String canonicalTargetPath = targetFile.getCanonicalPath();

            // 补充路径分隔符，避免前缀误判
            String expectedPrefix = canonicalBaseDir + File.separator;
            return canonicalTargetPath.startsWith(expectedPrefix);
        } catch (IOException e) {
            // 路径解析失败（如权限问题），直接判定为非法
            return false;
        }
    }
}
