@echo off
REM Gradle wrapper script for Windows — self-contained, no gradle-wrapper.jar required.
setlocal enabledelayedexpansion

REM Get script directory
set "APP_HOME=%~dp0"

REM --- 1. Read wrapper properties ---
set "PROPS=%APP_HOME%gradle\wrapper\gradle-wrapper.properties"
if not exist "%PROPS%" (
    echo ERROR: %PROPS% not found
    exit /b 1
)

REM Parse distribution URL from properties (and strip Gradle's \: escaping)
for /f "tokens=2 delims==" %%a in ('findstr /b "distributionUrl" "%PROPS%"') do set "DIST_URL=%%a"
if "%DIST_URL%"=="" (
    echo ERROR: distributionUrl not found in %PROPS%
    exit /b 1
)
REM Strip \: escaping used by Gradle properties files
set "DIST_URL=%DIST_URL:\:=:%"

REM --- 2. Find Java ---
set "JAVACMD=java.exe"
if not "%JAVA_HOME%"=="" (
    if exist "%JAVA_HOME%\bin\java.exe" (
        set "JAVACMD=%JAVA_HOME%\bin\java.exe"
    ) else if exist "%JAVA_HOME%\jre\bin\java.exe" (
        set "JAVACMD=%JAVA_HOME%\jre\bin\java.exe"
    )
)

%JAVACMD% -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java not found. Please install JDK 17+ or set JAVA_HOME.
    exit /b 1
)

REM --- 3. Download Gradle if needed ---
set "GRADLE_USER_HOME=%USERPROFILE%\.gradle"

REM Extract filename from URL (e.g., "gradle-8.5-bin.zip")
for %%F in ("%DIST_URL%") do set "DIST_ZIP=%%~nxF"
set "DIST_NAME=%DIST_ZIP:-bin.zip=%"

REM Compute a simple hash from the URL for the cache subdirectory
REM PowerShell can compute MD5 to be consistent across runs
set "HASH=default"
for /f %%h in ('powershell -Command "[System.BitConverter]::ToString(([System.Security.Cryptography.MD5]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes('%DIST_URL%')))).Replace('-','').ToLower().Substring(0,8)" 2^>nul') do set "HASH=%%h"

set "GRADLE_DIR=%GRADLE_USER_HOME%\wrapper\dists\%DIST_NAME%\%HASH%"

if not exist "%GRADLE_DIR%\%DIST_NAME%\bin\gradle.bat" (
    echo Downloading Gradle %DIST_NAME%...
    if not exist "%GRADLE_DIR%" mkdir "%GRADLE_DIR%"

    set "ZIP_FILE=%GRADLE_DIR%\%DIST_ZIP%"

    REM Download via PowerShell
    echo Downloading from %DIST_URL%...
    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%DIST_URL%' -OutFile '%ZIP_FILE%' -TimeoutSec 120; Write-Host 'OK' } catch { Write-Host 'FAILED:' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo ERROR: Failed to download Gradle. Check your network connection.
        exit /b 1
    )

    echo Extracting...
    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%GRADLE_DIR%'); Write-Host 'OK' } catch { Write-Host 'FAILED: ' + $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo ERROR: Failed to extract Gradle. Ensure the zip file is valid.
        exit /b 1
    )

    del "%ZIP_FILE%" >nul 2>&1
)

REM --- 4. Run Gradle ---
set "GRADLE_CMD=%GRADLE_DIR%\%DIST_NAME%\bin\gradle.bat"
if not exist "%GRADLE_CMD%" (
    echo ERROR: Gradle not found at %GRADLE_CMD%
    dir "%GRADLE_DIR%" /b
    exit /b 1
)

echo Running Gradle %DIST_NAME%...
call "%GRADLE_CMD%" %*
exit /b %errorlevel%
