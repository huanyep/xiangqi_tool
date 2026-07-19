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

REM Parse distribution URL from properties
for /f "tokens=2 delims==" %%a in ('findstr /b "distributionUrl" "%PROPS%"') do set "DIST_URL=%%a"
if "%DIST_URL%"=="" (
    echo ERROR: distributionUrl not found in %PROPS%
    exit /b 1
)

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
if not "%GRADLE_USER_HOME%"=="" set "GRADLE_CACHE=%GRADLE_USER_HOME%\wrapper\dists"

REM Extract version from URL (e.g., "gradle-8.5-bin.zip")
set "DIST_ZIP=%DIST_URL:*/=%
set "DIST_NAME=%DIST_ZIP:-bin.zip=%"

REM Cache dir: %GRADLE_USER_HOME%\wrapper\dists\%DIST_NAME%\<hash>\
REM We'll use first 8 chars of DIST_URL as simple hash
set "URL_HASH_TEMP=%DIST_URL%"
set "HASH=0"
for %%A in ("%DIST_URL%") do set "HASH=%%~zA"
if "%HASH%"=="0" set "HASH=default"

set "GRADLE_DIR=%GRADLE_USER_HOME%\wrapper\dists\%DIST_NAME%\%HASH%"

if not exist "%GRADLE_DIR%\%DIST_NAME%\bin\gradle.bat" (
    echo Downloading Gradle %DIST_NAME%...
    if not exist "%GRADLE_DIR%" mkdir "%GRADLE_DIR%"

    set "ZIP_FILE=%GRADLE_DIR%\%DIST_ZIP%"

    REM Try PowerShell first
    powershell -Command "try { echo 'Downloading from %DIST_URL%...'; Invoke-WebRequest -Uri '%DIST_URL%' -OutFile '%ZIP_FILE%' -TimeoutSec 120; Write-Host 'OK' } catch { Write-Host 'FAILED'; exit 1 }" >nul 2>&1

    if not exist "!ZIP_FILE!" (
        echo ERROR: Failed to download Gradle from %DIST_URL%
        echo Please check your network connection.
        exit /b 1
    )

    echo Extracting...
    powershell -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%GRADLE_DIR%'); Write-Host 'OK' } catch { Write-Host 'FAILED: ' + $_.Exception.Message; exit 1 }" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Failed to extract Gradle. Ensure %ZIP_FILE% is a valid zip file.
        exit /b 1
    )
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
