# ==============================================================================
# Script para empaquetar la versión actualizada de Spotlight on Proxmox VE (v1.1.0)
# ==============================================================================

$projectRoot = $PSScriptRoot
$outputZip = Join-Path $projectRoot "spotlight-proxmox-v1.1-update.zip"
$tempDir = Join-Path $projectRoot ".build_package"

Write-Host "Iniciando empaquetado de producción..." -ForegroundColor Cyan

if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
if (Test-Path $outputZip) {
    Remove-Item -Force $outputZip
}

New-Item -ItemType Directory -Path $tempDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/app") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/app/static") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/data") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/scripts") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "scripts") | Out-Null

# Copiar archivos principales de la aplicación (excluyendo __pycache__)
Get-ChildItem -Path (Join-Path $projectRoot "Dashboard/app") -Exclude "__pycache__" | Copy-Item -Destination (Join-Path $tempDir "Dashboard/app/") -Recurse -Force
Copy-Item -Force (Join-Path $projectRoot "Dashboard/Dockerfile") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/docker-compose.yml") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/requirements.txt") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/.env.example") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/setup_proxmox_guide.md") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/README.md") (Join-Path $tempDir "Dashboard/")
Copy-Item -Recurse -Force (Join-Path $projectRoot "Dashboard/scripts/*") (Join-Path $tempDir "Dashboard/scripts/")
Copy-Item -Recurse -Force (Join-Path $projectRoot "scripts/*") (Join-Path $tempDir "scripts/")
Copy-Item -Force (Join-Path $projectRoot "scripts/deploy_to_destination.sh") (Join-Path $tempDir "deploy_to_destination.sh")
Copy-Item -Force (Join-Path $projectRoot "README.md") (Join-Path $tempDir "README.md")

# Crear script de actualización directo en la raíz del paquete (alias de deploy_to_destination.sh)
$installScriptContent = @'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/deploy_to_destination.sh" "$@"
'@

$installScriptPath = Join-Path $tempDir "install_update.sh"
[System.IO.File]::WriteAllText($installScriptPath, $installScriptContent.Replace("`r`n", "`n"), [System.Text.Encoding]::UTF8)

# Comprimir a archivo zip
Compress-Archive -Path "$tempDir/*" -DestinationPath $outputZip -Force

# Intentar generar también .tar.gz si tar está disponible
if (Get-Command tar -ErrorAction SilentlyContinue) {
    $outputTar = Join-Path $projectRoot "spotlight-proxmox-v1.1-update.tar.gz"
    tar -czf $outputTar -C $tempDir .
    Write-Host "Paquete TAR.GZ generado: $outputTar" -ForegroundColor Green
}

# Limpiar directorio temporal
Remove-Item -Recurse -Force $tempDir

Write-Host "Paquete ZIP generado exitosamente: $outputZip" -ForegroundColor Green
