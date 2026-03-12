# 1. 环境初始化
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

# 根据 .opencode 切割路径并切换
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot
Write-Host "已切换至项目根目录: $ProjectRoot" -ForegroundColor Green


# 2. 读取 .env 并设置环境变量
$envFile = Join-Path $ProjectRoot ".opencode\skills\utils\scripts\.env"
Write-Host "正在加载配置文件: $envFile" -ForegroundColor Gray

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim() # 去掉行首尾空格
        if ($line.Contains('=') -and -not $line.StartsWith('#')) {
            $parts = $line.Split('=', 2)
            $key = $parts[0].Trim()
            # 关键修复：去掉引号的同时，再次 Trim() 确保没有任何尾随空格
            $value = $parts[1].Trim().Trim("'").Trim("`"").Trim() 
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# 3. --- 自动化核心：动态路径关联 ---
if (-not $env:DEVECO_HOME) {
    Write-Error "错误: .env 文件中未配置 DEVECO_HOME"
    exit 1
}


# 动态生成并强制校验
$RawSdkPath = Join-Path $env:DEVECO_HOME "sdk"
if (Test-Path $RawSdkPath) {
    $env:DEVECO_SDK_HOME = $RawSdkPath
    Write-Host "SDK 路径验证成功: $env:DEVECO_SDK_HOME" -ForegroundColor Green
} else {
    Write-Host "警告: 拼接后的路径无效 -> [$RawSdkPath]" -ForegroundColor Red
    Write-Warning "请检查 .env 文件中 DEVECO_HOME 的结尾是否有空格！"
    exit 1
}

# 修改脚本中的这一块
if (-not $env:DEVECO_SDK_HOME) {
    # 使用 Join-Path 拼接，并确保它是一个绝对路径
    $rawPath = Join-Path $env:DEVECO_HOME "sdk"
    $env:DEVECO_SDK_HOME = $rawPath
    Write-Host "已自动关联 SDK 路径: $env:DEVECO_SDK_HOME" -ForegroundColor Gray
}

# 动态获取当前用户家目录下的 Cangjie SDK (消除 maruide 硬编码)
$CangjieSdkRoot = Join-Path $env:USERPROFILE ".cangjie-sdk\6.0\cangjie"
if (Test-Path $CangjieSdkRoot) {
    $env:PATH = "$CangjieSdkRoot\bin;$CangjieSdkRoot\lib;$CangjieSdkRoot\build-tools\tools\bin;" + $env:PATH
    Write-Host "已动态注入 Cangjie SDK 环境" -ForegroundColor Cyan
} else {
    Write-Warning "警告: 未在 $CangjieSdkRoot 找到仓颉 SDK"
}

# 4. 设置工具路径
$OhpmPath = Join-Path $env:DEVECO_HOME "tools\ohpm\bin\ohpm.bat"
$nodeExe = Join-Path $env:DEVECO_HOME "tools\node\node.exe"
$hvigorwJs = Join-Path $env:DEVECO_HOME "tools\hvigor\bin\hvigorw.js"

# 5. 执行构建流程
Write-Host "开始安装依赖..." -ForegroundColor Magenta
if (Test-Path $OhpmPath) {
    & $OhpmPath install --all --registry https://ohpm.openharmony.cn/ohpm/ --strict_ssl true
}

Write-Host "执行 SyncCangjieResource..." -ForegroundColor Magenta
$argList1 = @($hvigorwJs, '--mode', 'module', '-p', 'module=entry@default', 'SyncCangjieResource', '--analyze=normal', '--parallel', '--incremental', '--daemon')
& $nodeExe $argList1

Write-Host "执行 assembleHap..." -ForegroundColor Magenta
$argList2 = @($hvigorwJs, '--mode', 'module', '-p', 'product=default', 'assembleHap', '--analyze=normal', '--parallel', '--incremental', '--daemon')
& $nodeExe $argList2

# Write-Host "构建任务完成！" -ForegroundColor Green