$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $root
$buildDir = Join-Path $root ".build"
$pdfDir = Join-Path $workspaceRoot "pdf"
$styleDir = Join-Path $root "style"
$miktexBin = Join-Path $env:LOCALAPPDATA "Programs\MiKTeX\miktex\bin\x64"

$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
$biber = Get-Command biber -ErrorAction SilentlyContinue

if (-not $pdflatex) {
    $pdflatexPath = Join-Path $miktexBin "pdflatex.exe"
    if (Test-Path $pdflatexPath) {
        $pdflatex = $pdflatexPath
    }
}

if (-not $biber) {
    $biberPath = Join-Path $miktexBin "biber.exe"
    if (Test-Path $biberPath) {
        $biber = $biberPath
    }
}

if (-not $pdflatex) {
    throw "No se encontro pdflatex. Instala MiKTeX o agrega MiKTeX al PATH."
}

if (-not $biber) {
    throw "No se encontro biber. Instala MiKTeX o agrega MiKTeX al PATH."
}

if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

if (-not (Test-Path $pdfDir)) {
    New-Item -ItemType Directory -Path $pdfDir | Out-Null
}

Push-Location $root
try {
    $previousTexInputs = $env:TEXINPUTS
    $env:TEXINPUTS = "$styleDir;$previousTexInputs"

    & $pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$buildDir" main.tex
    & $biber --input-directory "$buildDir" --output-directory "$buildDir" main
    & $pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$buildDir" main.tex
    & $pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$buildDir" main.tex

    $sourcePdf = Join-Path $buildDir "main.pdf"
    $targetPdf = Join-Path $pdfDir "main.pdf"

    if (Test-Path $targetPdf) {
        Remove-Item -LiteralPath $targetPdf -Force
    }

    Move-Item -Path $sourcePdf -Destination $targetPdf -Force
}
finally {
    $env:TEXINPUTS = $previousTexInputs
    Pop-Location
}
