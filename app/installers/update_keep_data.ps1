# Bring the saved data from an earlier copy of the app into this new copy:
# hitch setups, crew rosters, signatures, TRA/TBT History and timesheets.
# Run by "UPDATE - keep existing data.bat", which then runs the normal
# installer (that repoints the desktop/start-up shortcuts to this copy).
# The old folder is only read, never changed -- it stays as a backup.

$ErrorActionPreference = "Stop"
$NewApp = Split-Path $PSScriptRoot -Parent                 # ...\DOUS Deckhand\app
$NewData = Join-Path $NewApp "app_data"
# Caches/logs and this copy's own template fingerprints are not carried over.
$Skip = @("template_baselines.json", "template_catalog.json", "app.log", "app.log.old", "setup.json")

function Find-OldDataDirs {
    $found = [System.Collections.Generic.List[string]]::new()
    $sh = New-Object -ComObject WScript.Shell
    $linkDirs = if ($env:DOUS_LINK_DIR) { @($env:DOUS_LINK_DIR) }   # (testing only)
                else { @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Startup')) }
    foreach ($dir in $linkDirs) {
        # current name, plus the name used before v1.1 ("DOUS TRA-TBT App")
        Get-ChildItem -LiteralPath $dir -Filter "DOUS*.lnk" -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -like "DOUS Deckhand*" -or $_.Name -like "DOUS TRA-TBT App*" } | ForEach-Object {
            $l = $sh.CreateShortcut($_.FullName)
            # Python version: pythonw.exe "<app>\start_app.pyw"; .exe version: <folder>\DOUS Deckhand.exe
            if ($l.Arguments -match '"([^"]+\.pyw)"') { $found.Add((Join-Path (Split-Path $Matches[1]) "app_data")) }
            elseif ($l.TargetPath -like "*.exe" -and $l.TargetPath -notlike "*pythonw.exe") { $found.Add((Join-Path (Split-Path $l.TargetPath) "app_data")) }
        }
    }
    if (-not $env:DOUS_LINK_DIR) {
        $places = @("C:", "C:\DOUS HSE", "$env:USERPROFILE\Downloads", "$env:USERPROFILE\Downloads\DOUS HSE",
                    "$env:USERPROFILE\Desktop", "$env:USERPROFILE\Desktop\DOUS HSE")
        # folder named "DOUS Deckhand" now, "TRA App" before v1.1
        foreach ($p in ($places | ForEach-Object { "$_\DOUS Deckhand\app\app_data"; "$_\TRA App\app\app_data" })) {
            $found.Add($p)
        }
    }
    $new = (Resolve-Path -LiteralPath $NewData -ErrorAction SilentlyContinue).Path
    $found | Where-Object { Test-Path -LiteralPath $_ } |
        ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
        Where-Object { $_ -ne $new -and ((Test-Path (Join-Path $_ "hitches")) -or (Test-Path (Join-Path $_ "hitch.json")) -or (Test-Path (Join-Path $_ "signatures.json"))) } |
        Select-Object -Unique
}

function Describe($dir) {
    $h = @(Get-ChildItem (Join-Path $dir "hitches") -Filter *.json -ErrorAction SilentlyContinue).Count
    if ($h -eq 0 -and (Test-Path (Join-Path $dir "hitch.json"))) { $h = 1 }
    $s = @(Get-ChildItem (Join-Path $dir "signatures") -File -ErrorAction SilentlyContinue).Count
    $d = @(Get-ChildItem (Join-Path $dir "days") -Recurse -Filter *.json -ErrorAction SilentlyContinue).Count
    "$h hitch setup(s), $s signature(s), $d day(s) of History"
}

Write-Host "UPDATE - DOUS Deckhand"
Write-Host ("=" * 40)
$candidates = @(Find-OldDataDirs)
if ($candidates.Count -eq 0) {
    Write-Host "`nNo earlier copy of the app was found on this computer."
    $manual = Read-Host "If it's somewhere else, paste the path of its DOUS Deckhand folder (or press Enter to skip)"
    if ($manual) {
        $try = @((Join-Path $manual "app\app_data"), (Join-Path $manual "app_data")) | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($try) { $candidates = @((Resolve-Path $try).Path) } else { Write-Host "No saved data found there." }
    }
}
if ($candidates.Count -eq 0) {
    Write-Host "`nNothing to bring over - continuing as a fresh install."
    exit 0
}

$old = $candidates[0]
if ($candidates.Count -gt 1) {
    Write-Host "`nMore than one earlier copy was found:"
    for ($i = 0; $i -lt $candidates.Count; $i++) { Write-Host ("  {0}. {1}  ({2})" -f ($i + 1), $candidates[$i], (Describe $candidates[$i])) }
    $pick = Read-Host "Type the number to bring over (Enter = 1)"
    if ($pick -match '^\d+$' -and [int]$pick -ge 1 -and [int]$pick -le $candidates.Count) { $old = $candidates[[int]$pick - 1] }
}

Write-Host "`nFound your current data in:`n    $old`n    ($(Describe $old))"
$ok = Read-Host "Bring it into this new version? (Y/N, Enter = Y)"
if ($ok -and $ok.Trim().ToUpper() -ne "Y") { Write-Host "Skipped - continuing as a fresh install."; exit 0 }

# Stop the running app so nothing is mid-write while copying.
Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($p -and ($p.ProcessName -like "python*" -or $p.ProcessName -eq "DOUS Deckhand" -or $p.ProcessName -eq "TRA App")) { Stop-Process -Id $p.Id -Force }
}
Start-Sleep -Seconds 1

New-Item -ItemType Directory -Force $NewData | Out-Null
$copied = 0
Get-ChildItem -LiteralPath $old -Force | Where-Object { $Skip -notcontains $_.Name } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $NewData -Recurse -Force
    $copied++
}
Write-Host "`nCopied $copied item(s): $(Describe $NewData)"
Write-Host "Your old folder has NOT been changed. Once you've checked everything is"
Write-Host "in the new version, you can delete it:`n    $(Split-Path (Split-Path $old -Parent) -Parent)"
Write-Host "`nNow running the installer to point the shortcuts at the new version..."
exit 0
