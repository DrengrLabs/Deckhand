# Sets up Topaz SigWeb for the DOUS signature pad (Topaz T-LBK460).
# Run elevated by "INSTALL - run once.bat" (one Windows permission prompt).
#   1. Installs SigWeb from sigweb.exe beside this script, if it isn't
#      installed yet.
#   2. Writes the pad model into SigWeb's settings file -- the same three
#      values the Topaz installer saves when T-LBK460 is chosen -- so it
#      doesn't matter what (if anything) was picked during the install.
#   3. Restarts the SigWeb service so it picks the settings up.
param(
    [string]$IniPath = "$env:WINDIR\SigPlus.ini",   # overridable for testing
    [switch]$SkipInstall,
    [switch]$SkipService
)

$ErrorActionPreference = "Stop"
# TabletType 6 = Topaz "HSB" (USB/HID) connection -- what every -HSB pad
# uses. For type 6 Topaz ignores TabletComPort; 9 is simply the value the
# Topaz installer itself writes, kept so the file matches it exactly.
# (A pad on an old serial/COM cable would need TabletType 0 instead.)
$Settings = [ordered]@{
    TabletType    = "6"
    TabletComPort = "9"
    TabletModel   = "SigLiteLCD1X5"
}

function Test-SigWebInstalled {
    [bool](Get-Service -Name SigREST -ErrorAction SilentlyContinue)
}

try {
    if (-not $SkipInstall -and -not (Test-SigWebInstalled)) {
        $setup = Join-Path $PSScriptRoot "sigweb.exe"
        if (-not (Test-Path $setup)) { throw "sigweb.exe not found next to this script." }
        Write-Host "Installing Topaz SigWeb - click through the Topaz installer, accepting the defaults."
        Write-Host "(The pad model is set automatically afterwards.)"
        Start-Process -FilePath $setup -Wait
    }

    if (-not (Test-Path $IniPath)) {
        throw "SigWeb's settings file wasn't found at $IniPath - was SigWeb installed?"
    }

    # Change just those keys inside the [Tablet] section; leave the rest alone.
    $lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $IniPath)
    $start = $lines.FindIndex({ param($l) $l.Trim() -ieq "[Tablet]" })
    if ($start -lt 0) { $lines.Insert(0, "[Tablet]"); $start = 0 }
    $end = $lines.Count
    for ($i = $start + 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim().StartsWith("[")) { $end = $i; break }
    }
    foreach ($key in $Settings.Keys) {
        $found = $false
        for ($i = $start + 1; $i -lt $end; $i++) {
            if ($lines[$i] -match "^\s*$key\s*=") { $lines[$i] = "$key=$($Settings[$key])"; $found = $true; break }
        }
        if (-not $found) { $lines.Insert($end, "$key=$($Settings[$key])"); $end++ }
    }
    if (-not (Test-Path "$IniPath.dous-backup")) { Copy-Item -LiteralPath $IniPath "$IniPath.dous-backup" }
    Set-Content -LiteralPath $IniPath -Value $lines -Encoding ASCII
    Write-Host "Signature pad set to Topaz T-LBK460."

    if (-not $SkipService -and (Test-SigWebInstalled)) {
        Restart-Service -Name SigREST
        Write-Host "SigWeb service restarted."
    }
    exit 0
}
catch {
    Write-Host ""
    Write-Host "Topaz SigWeb setup didn't finish: $($_.Exception.Message)"
    Write-Host "The app still works - signatures can be drawn with the mouse until this is fixed."
    Start-Sleep -Seconds 8
    exit 1
}
