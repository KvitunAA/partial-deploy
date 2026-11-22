# Блокирует и завершает сеансы только целевой информационной базы.
# Серверная база: rac (блокировка начала сеансов + terminate сеансов этой базы).
# Файловая база: завершение процессов, в командной строке которых есть путь этой базы.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("block", "unblock")]
    [string]$Action,
    [string]$Srv = "",
    [string]$Ref = "",
    [string]$FileIb = "",
    [string]$Platform = "",
    [string]$User = "",
    [string]$Password = "",
    [string]$LogDir = ""
)

$ErrorActionPreference = "Stop"
$PermissionCode = "partialdeploy"
$DeniedMessage = "Частичная загрузка конфигурации. Подождите."

function Get-RacPath {
    param([string]$PlatformPath)
    $candidates = @()
    if ($PlatformPath) {
        $bin = Split-Path -Parent $PlatformPath
        $candidates += (Join-Path $bin "rac.exe")
    }
    if ($env:RAC) { $candidates += $env:RAC }
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path)) { return $path }
    }
    return $null
}

function Get-RasAddress {
    param([string]$ServerName)
    if ($env:RAS) { return $env:RAS }
    $hostName = ($ServerName -split ":", 2)[0]
    if (-not $hostName) { throw "Не задан SRV, адрес RAS не из чего собрать." }
    return "${hostName}:1545"
}

function Invoke-Rac {
    param([string]$RacPath, [string[]]$Arguments)
    $output = & $RacPath @Arguments 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "rac завершился с кодом ${LASTEXITCODE}: $output"
    }
    return $output
}

function Parse-RacRecords {
    param([string]$Text)
    $records = @()
    $current = @{}
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line.Trim() -eq "") {
            if ($current.Count -gt 0) {
                $records += ,$current
                $current = @{}
            }
            continue
        }
        if ($line -match '^\s*([^:]+?)\s*:\s*(.*)$') {
            $current[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    if ($current.Count -gt 0) { $records += ,$current }
    return $records
}

function Get-ClusterArgs {
    $args = @()
    if ($env:CLUSTER_USER) { $args += "--cluster-user=$($env:CLUSTER_USER)" }
    if ($null -ne $env:CLUSTER_PWD -and $env:CLUSTER_PWD -ne "") {
        $args += "--cluster-pwd=$($env:CLUSTER_PWD)"
    }
    return $args
}

function Find-TargetInfobase {
    param([string]$RacPath, [string]$RasAddress, [string]$InfobaseName)
    $clusterArgs = Get-ClusterArgs
    $clusters = Parse-RacRecords (Invoke-Rac $RacPath (@($RasAddress, "cluster", "list") + $clusterArgs))
    if ($env:CLUSTER_ID) {
        $clusters = @($clusters | Where-Object { $_.cluster -eq $env:CLUSTER_ID })
    }
    $found = @()
    foreach ($cluster in $clusters) {
        $clusterId = $cluster.cluster
        if (-not $clusterId) { continue }
        $list = Parse-RacRecords (Invoke-Rac $RacPath (@(
            $RasAddress, "infobase", "summary", "list", "--cluster=$clusterId"
        ) + $clusterArgs))
        foreach ($item in $list) {
            if ($item.name -and ($item.name -eq $InfobaseName)) {
                $found += [pscustomobject]@{
                    Cluster = $clusterId
                    Infobase = $item.infobase
                    Name = $item.name
                }
            }
        }
    }
    if ($found.Count -eq 0) {
        throw "В кластере нет информационной базы с именем '$InfobaseName'. Другие базы не изменялись."
    }
    if ($found.Count -gt 1) {
        throw "Имя '$InfobaseName' найдено в нескольких кластерах. Задайте CLUSTER_ID в deploy-local.cmd."
    }
    return $found[0]
}

function Set-SessionDeny {
    param(
        [string]$RacPath,
        [string]$RasAddress,
        [string]$ClusterId,
        [string]$InfobaseId,
        [ValidateSet("on", "off")][string]$Deny,
        [string]$JobsDeny
    )
    $clusterArgs = Get-ClusterArgs
    $update = @(
        $RasAddress, "infobase", "update",
        "--cluster=$ClusterId",
        "--infobase=$InfobaseId",
        "--sessions-deny=$Deny",
        "--scheduled-jobs-deny=$JobsDeny"
    )
    if ($User) { $update += "--infobase-user=$User" }
    if ($Password) { $update += "--infobase-pwd=$Password" }
    if ($Deny -eq "on") {
        $update += "--permission-code=$PermissionCode"
        $update += "--denied-message=$DeniedMessage"
    }
    Invoke-Rac $RacPath ($update + $clusterArgs) | Out-Null
}

function Stop-InfobaseSessions {
    param(
        [string]$RacPath,
        [string]$RasAddress,
        [string]$ClusterId,
        [string]$InfobaseId
    )
    $clusterArgs = Get-ClusterArgs
    $sessions = Parse-RacRecords (Invoke-Rac $RacPath (@(
        $RasAddress, "session", "list",
        "--cluster=$ClusterId",
        "--infobase=$InfobaseId"
    ) + $clusterArgs))
    $count = 0
    foreach ($session in $sessions) {
        $sessionId = $session.session
        if (-not $sessionId) { continue }
        Invoke-Rac $RacPath (@(
            $RasAddress, "session", "terminate",
            "--cluster=$ClusterId",
            "--session=$sessionId"
        ) + $clusterArgs) | Out-Null
        $count++
    }
    return $count
}

function Test-PathInCommandLine {
    param([string]$CommandLine, [string]$InfobasePath)
    $cmd = $CommandLine.ToLower().Replace("/", "\")
    $path = $InfobasePath.ToLower().Trim().Trim('"').TrimEnd("\")
    if (-not $path) { return $false }
    $start = 0
    while (($index = $cmd.IndexOf($path, $start)) -ge 0) {
        $after = $index + $path.Length
        if ($after -ge $cmd.Length) { return $true }
        if (@('"', "'", " ", ";", "\") -contains $cmd[$after]) { return $true }
        $start = $after
    }
    return $false
}

function Stop-FileInfobaseProcesses {
    param([string]$InfobasePath)
    $names = @("1cv8.exe", "1cv8c.exe", "1cv8s.exe")
    $stopped = 0
    $processes = Get-CimInstance Win32_Process -Filter "Name = '1cv8.exe' OR Name = '1cv8c.exe' OR Name = '1cv8s.exe'"
    foreach ($process in $processes) {
        if ($names -notcontains $process.Name) { continue }
        if (-not (Test-PathInCommandLine $process.CommandLine $InfobasePath)) { continue }
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Output "Завершён процесс $($process.Name) pid=$($process.ProcessId) этой файловой базы."
        $stopped++
    }
    return $stopped
}

if ($FileIb) {
    if ($Action -eq "unblock") { exit 0 }
    $stopped = Stop-FileInfobaseProcesses $FileIb
    Write-Output "Файловая база: завершено процессов с этим путём: $stopped. Сеансы других баз не завершались."
    exit 0
}

if (-not $Srv -or -not $Ref) {
    throw "Для серверной базы нужны SRV и REF."
}

$rac = Get-RacPath $Platform
$marker = $null
if ($LogDir) { $marker = Join-Path $LogDir "session-lock-owned.txt" }

if ($Action -eq "unblock" -and -not ($marker -and (Test-Path -LiteralPath $marker))) { exit 0 }

if (-not $rac) {
    if ($Action -eq "block") {
        Write-Output "rac.exe рядом с платформой не найден. Блокировку кластера не ставил."
        Write-Output "Сеансы этой базы завершит конфигуратор ключом -SessionTerminate force. Другие базы не завершаются."
        exit 0
    }
    exit 0
}

$ras = Get-RasAddress $Srv
$target = Find-TargetInfobase $rac $ras $Ref
$clusterArgs = Get-ClusterArgs
$infoRecords = Parse-RacRecords (Invoke-Rac $rac (@(
    $ras, "infobase", "info",
    "--cluster=$($target.Cluster)",
    "--infobase=$($target.Infobase)"
) + $clusterArgs))
$info = @{}
if ($infoRecords.Count -gt 0) { $info = $infoRecords[0] }
$jobsDeny = $info."scheduled-jobs-deny"
if (-not $jobsDeny) { $jobsDeny = "off" }

if ($Action -eq "unblock") {
    $savedJobs = (Get-Content -LiteralPath $marker -Raw).Trim()
    if (-not $savedJobs) { $savedJobs = "off" }
    Set-SessionDeny $rac $ras $target.Cluster $target.Infobase "off" $savedJobs
    Remove-Item -LiteralPath $marker -Force
    $ucFile = Join-Path $LogDir "session-uc.txt"
    if (Test-Path -LiteralPath $ucFile) { Remove-Item -LiteralPath $ucFile -Force }
    Write-Output "Блокировка начала сеансов снята с базы '$Ref'."
    exit 0
}

if ($info."sessions-deny" -eq "on") {
    Write-Output "У базы '$Ref' уже включена блокировка начала сеансов. Чужую блокировку не меняю."
    $existingCode = $info."permission-code"
    if ($existingCode -and $LogDir) {
        Set-Content -LiteralPath (Join-Path $LogDir "session-uc.txt") -Value $existingCode -Encoding ASCII
    }
} else {
    Set-SessionDeny $rac $ras $target.Cluster $target.Infobase "on" "on"
    if ($marker) {
        Set-Content -LiteralPath $marker -Value $jobsDeny -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $LogDir "session-uc.txt") -Value $PermissionCode -Encoding ASCII
    }
}
$stopped = Stop-InfobaseSessions $rac $ras $target.Cluster $target.Infobase
Write-Output "База '$Ref': завершено сеансов этой базы: $stopped. Другие базы не изменялись."
exit 0
