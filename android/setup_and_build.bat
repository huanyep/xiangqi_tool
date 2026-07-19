@echo off
chcp 65001 >nul
title 象棋辅助 APK 构建
echo ========================================
echo   象棋辅助 APK 构建工具
echo ========================================
echo.

:: 检查 Java
where java >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] 未找到 Java, 请安装 JDK 17+
    echo    下载: https://adoptium.net/
    echo    安装后重启此脚本
    pause
    exit /b 1
)
echo [OK] Java:
java -version 2>&1 | findstr "version"

:: 检查 Gradle
set GRADLE_HOME=%USERPROFILE%\.gradle
if not exist "%GRADLE_HOME%\wrapper\dists\gradle-8.5-*" (
    echo [*] 首次运行需要下载 Gradle (自动)
)

:: 创建 wrapper (如果没有)
if not exist "gradlew.bat" (
    echo [*] 生成 Gradle wrapper...
    gradle wrapper --gradle-version 8.5
)

:: 设置 ANDROID_HOME
if "%ANDROID_HOME%"=="" (
    if exist "C:\Users\%USERNAME%\AppData\Local\Android\Sdk" (
        set ANDROID_HOME=C:\Users\%USERNAME%\AppData\Local\Android\Sdk
    ) else if exist "C:\Android\Sdk" (
        set ANDROID_HOME=C:\Android\Sdk
    ) else (
        echo [!] 未找到 Android SDK
        echo    请安装 Android Studio
        echo    或设置 ANDROID_HOME 环境变量
        pause
        exit /b 1
    )
)
echo [OK] Android SDK: %ANDROID_HOME%

:: 构建
echo.
echo [*] 构建 APK...
call gradlew assembleDebug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] 构建成功!
    echo APK 位置: app\build\outputs\apk\debug\app-debug.apk
    echo.
    echo 安装方法:
    echo   1. 手机开启「开发者选项」和「USB 调试」
    echo   2. 连接电脑, 运行: gradlew installDebug
    echo   3. 或直接把 APK 传到手机上安装
) else (
    echo.
    echo [!] 构建失败, 检查上方错误信息
)

pause
