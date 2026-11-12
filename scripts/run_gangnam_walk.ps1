param(
    [ValidateSet('Check','Map','Batch','Editor')][string]$Mode='Check',
    [ValidatePattern('^[a-z0-9_-]{1,48}$')][string]$RunId=('walk-'+[guid]::NewGuid().ToString('N').Substring(0,8)),
    [string]$EditorRoot="$env:LOCALAPPDATA/AccessibleWayfinding/unity-editor/6000.3.28f1/Editor",
    [string]$VisionPython="$env:LOCALAPPDATA/AccessibleWayfinding/vision-venv/Scripts/python.exe"
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$unityProject=Join-Path $projectRoot 'unity/AccessibleStation'
$dataRoot=Join-Path $env:LOCALAPPDATA 'AccessibleWayfinding/research'
$previousRun=$env:WAYFINDING_WALK_RUN
$previousEncoding=$env:PYTHONIOENCODING
Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONIOENCODING='utf-8'
    if($env:WAYFINDING_RESEARCH_DATA -and [IO.Path]::GetFullPath($env:WAYFINDING_RESEARCH_DATA) -ne [IO.Path]::GetFullPath($dataRoot)){throw 'Unity currently uses the default LOCALAPPDATA research directory.'}
    foreach($binary in @($VisionPython,(Join-Path $EditorRoot 'Unity.com'))){if(-not(Test-Path -LiteralPath $binary)){throw "Required executable missing: $binary"}}
    $map=Join-Path $dataRoot 'gangnam-walk/map/map.npz'
    if($Mode -eq 'Check'){
        Write-Output "Synthetic map present: $(Test-Path -LiteralPath $map)"
        try{Invoke-RestMethod 'http://127.0.0.1:8768/health' -TimeoutSec 2 | ConvertTo-Json -Compress}catch{Write-Output 'Image bridge is not running.'}
        return
    }
    if(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'Unity.exe' -and $_.CommandLine -like '*AccessibleStation*' -and $_.CommandLine -notlike '*-adb2*'}){throw 'Close the Unity Editor for this project before launching another run.'}
    New-Item -ItemType Directory -Path (Join-Path $projectRoot 'runtime') -Force | Out-Null
    if($Mode -eq 'Map'){
        if(Test-Path -LiteralPath $map){throw 'Existing map retained. Archive previous mapping evidence before making a new map.'}
        & $VisionPython -m research.gangnam_walk_prepare
        if($LASTEXITCODE -ne 0){throw 'Scene preparation failed.'}
        & (Join-Path $EditorRoot 'Unity.com') -batchmode -quit -projectPath $unityProject -executeMethod GangnamWalkBuilder.CaptureMap -logFile (Join-Path $projectRoot 'runtime/gangnam-walk-map.log')
        if($LASTEXITCODE -ne 0){throw 'Map rendering failed.'}
        & $VisionPython -m research.gangnam_walk_map
        if($LASTEXITCODE -ne 0){throw 'Map feature extraction failed.'}
        return
    }
    if(-not(Test-Path -LiteralPath $map)){throw 'Run Map first.'}
    $ready=$false
    try{$h=Invoke-RestMethod 'http://127.0.0.1:8768/health' -TimeoutSec 2;$ready=$h.ready -and $h.service -eq 'gangnam-walk'}catch{}
    if(-not $ready){
        if(Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue){throw 'Port 8768 belongs to a different service.'}
        Start-Process -FilePath $VisionPython -ArgumentList '-m','uvicorn','research.gangnam_walk_service:app','--host','127.0.0.1','--port','8768','--no-access-log' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot "runtime/walk-service-$RunId.out.log") -RedirectStandardError (Join-Path $projectRoot "runtime/walk-service-$RunId.err.log")
        for($i=0;$i -lt 20;$i++){
            Start-Sleep -Milliseconds 500
            try{$h=Invoke-RestMethod 'http://127.0.0.1:8768/health' -TimeoutSec 2;$ready=$h.ready;if($ready){break}}catch{}
        }
        if(-not $ready){throw 'Image bridge did not start.'}
    }
    & $VisionPython -m research.gangnam_walk_snapshot --run $RunId
    if($LASTEXITCODE -ne 0){throw 'Cannot freeze run; choose an unused RunId.'}
    $env:WAYFINDING_WALK_RUN=$RunId
    if($Mode -eq 'Editor'){
        Start-Process -FilePath (Join-Path $EditorRoot 'Unity.exe') -ArgumentList ('-projectPath "{0}" -executeMethod GangnamWalkBuilder.Build -logFile "{1}"' -f $unityProject,(Join-Path $projectRoot "runtime/walk-$RunId.log")) -WindowStyle Normal
        Write-Output 'Press Play, then 직접 이동 시작. Right mouse + WASD, or the on-screen step button.'
    }else{
        & (Join-Path $EditorRoot 'Unity.com') -batchmode -projectPath $unityProject -executeMethod GangnamWalkBuilder.BuildAndRun -logFile (Join-Path $projectRoot "runtime/walk-$RunId.log")
        if($LASTEXITCODE -ne 0){throw 'Unity execution failed; raw evidence retained.'}
        & $VisionPython -m research.gangnam_walk_report --run $RunId
        if($LASTEXITCODE -ne 0){throw 'Scoring/export failed; raw evidence retained.'}
    }
}finally{$env:WAYFINDING_WALK_RUN=$previousRun;$env:PYTHONIOENCODING=$previousEncoding;Pop-Location}
