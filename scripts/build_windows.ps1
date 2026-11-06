$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$compilerCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$compiler = $compilerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup 6 is required. Install it from https://jrsoftware.org/isinfo.php."
}
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Push-Location $repositoryRoot
try {
    & $python -m PyInstaller --clean --noconfirm installer\studenthelper.spec
    if (-not $?) {
        throw "PyInstaller failed to build StudentHelper.exe."
    }

    & $compiler installer\studenthelper.iss
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed to create the StudentHelper installer."
    }
}
finally {
    Pop-Location
}

Write-Output "Installer created in dist\installer."
