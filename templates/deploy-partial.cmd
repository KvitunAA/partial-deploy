@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%deploy-local.cmd" (
    call "%ROOT%deploy-local.cmd"
) else (
    echo [ОШИБКА] Нет deploy-local.cmd
    echo Скопируйте deploy-local.cmd.example в deploy-local.cmd и задайте подключение и USER.
    exit /b 1
)

if not defined PLATFORM set "PLATFORM=C:\Program Files\1cv8\8.5.1.1522\bin\1cv8.exe"
if not defined SRC set "SRC=%ROOT%config"
if not defined LISTFILE set "LISTFILE=%ROOT%partial-deploy-list.txt"
if not defined LOGDIR set "LOGDIR=C:\temp\1c-partial-deploy"

set "CONN_READY="
if defined FILE_IB set "CONN_READY=1"
if defined SRV if defined REF set "CONN_READY=1"
if not defined CONN_READY (
    echo [ОШИБКА] Задайте SRV и REF или FILE_IB в deploy-local.cmd
    exit /b 1
)
if not defined USER (
    echo [ОШИБКА] USER не задан в deploy-local.cmd
    exit /b 1
)
if not exist "%PLATFORM%" (
    echo [ОШИБКА] Не найден 1cv8: "%PLATFORM%"
    exit /b 1
)
if not exist "%SRC%\Configuration.xml" (
    echo [ОШИБКА] Нет Configuration.xml: "%SRC%\Configuration.xml"
    exit /b 1
)
if not exist "%LISTFILE%" (
    echo [ОШИБКА] Нет списка: "%LISTFILE%"
    exit /b 1
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo.
echo === Частичная загрузка конфигурации ===
echo Платформа: %PLATFORM%
if defined FILE_IB (
    echo Подключ.:  File="%FILE_IB%";
) else (
    echo Подключ.:  Srvr="%SRV%";Ref="%REF%";
)
echo Пользов.:  %USER%
echo Источник:  %SRC%
echo Список:    %LISTFILE%
echo Логи:      %LOGDIR%
echo.
if /I "%CONFIRM%"=="YES" goto confirmed
set /p CONFIRM=Введите YES для продолжения:
if /I not "%CONFIRM%"=="YES" (
    echo Отменено.
    exit /b 1
)
:confirmed

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Process -Name '1cv8','1cv8c','1cv8s' -ErrorAction SilentlyContinue | Stop-Process -Force"
timeout /t 2 /nobreak >nul

set "LISTFILE_ASCII=%LOGDIR%\partial-list.txt"
copy /Y "%LISTFILE%" "%LISTFILE_ASCII%" >nul

set "LOG=%LOGDIR%\deploy-partial.log"
set "RESULT=%LOGDIR%\deploy-partial-result.txt"
del /F /Q "%LOG%" "%RESULT%" 2>nul

if defined FILE_IB (
    call :LoadConfig "File=""%FILE_IB%"";"
) else (
    call :LoadConfig "Srvr=""%SRV%"";Ref=""%REF%"";"
)

if not exist "%RESULT%" (
    echo [ОШИБКА] Нет DumpResult: "%RESULT%"
    exit /b 1
)
echo DumpResult:
type "%RESULT%"
findstr /B /C:"0" "%RESULT%" >nul || exit /b 1
echo Частичная загрузка успешна.
exit /b 0

:LoadConfig
if defined PASS (
    "%PLATFORM%" DESIGNER /IBConnectionString %1 /N "%USER%" /P "%PASS%" ^
      /LoadConfigFromFiles "%SRC%" -listFile "%LISTFILE_ASCII%" -partial -updateConfigDumpInfo ^
      /UpdateDBCfg Dynamic+ ^
      /Out "%LOG%" /DumpResult "%RESULT%" /DisableStartupMessages /DisableStartupDialogs
) else (
    "%PLATFORM%" DESIGNER /IBConnectionString %1 /N "%USER%" ^
      /LoadConfigFromFiles "%SRC%" -listFile "%LISTFILE_ASCII%" -partial -updateConfigDumpInfo ^
      /UpdateDBCfg Dynamic+ ^
      /Out "%LOG%" /DumpResult "%RESULT%" /DisableStartupMessages /DisableStartupDialogs
)
exit /b %ERRORLEVEL%