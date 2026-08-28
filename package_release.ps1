# ==============================================================================
# Script para empaquetar la versión actualizada de Spotlight on Proxmox VE (v1.1.0)
# ==============================================================================

$projectRoot = $PSScriptRoot
$outputZip = Join-Path $projectRoot "spotlight-proxmox-v1.1-update.zip"
$outputTar = Join-Path $projectRoot "spotlight-proxmox-v1.1-update.tar.gz"
$tempDir = Join-Path $projectRoot ".build_package"

Write-Host "Iniciando empaquetado de producción..." -ForegroundColor Cyan

if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
if (Test-Path $outputZip) {
    Remove-Item -Force $outputZip
}
if (Test-Path $outputTar) {
    Remove-Item -Force $outputTar
}

New-Item -ItemType Directory -Path $tempDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "app") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "data") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "scripts") | Out-Null

New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/app") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/data") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $tempDir "Dashboard/scripts") | Out-Null

# 1. Copiar a la raíz del paquete (para desempaque directo en ~/Dashboard)
Get-ChildItem -Path (Join-Path $projectRoot "Dashboard/app") -Exclude "__pycache__" | Copy-Item -Destination (Join-Path $tempDir "app/") -Recurse -Force
Copy-Item -Force (Join-Path $projectRoot "Dashboard/Dockerfile") (Join-Path $tempDir "")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/docker-compose.yml") (Join-Path $tempDir "")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/requirements.txt") (Join-Path $tempDir "")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/.env.example") (Join-Path $tempDir "")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/setup_proxmox_guide.md") (Join-Path $tempDir "")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/README.md") (Join-Path $tempDir "")
Copy-Item -Recurse -Force (Join-Path $projectRoot "scripts/*") (Join-Path $tempDir "scripts/")
Copy-Item -Force (Join-Path $projectRoot "scripts/install_offline.sh") (Join-Path $tempDir "install_offline.sh")
Copy-Item -Force (Join-Path $projectRoot "scripts/install_offline.sh") (Join-Path $tempDir "install.sh")
Copy-Item -Force (Join-Path $projectRoot "scripts/deploy_to_destination.sh") (Join-Path $tempDir "deploy_to_destination.sh")
Copy-Item -Force (Join-Path $projectRoot "README.md") (Join-Path $tempDir "README.md")

# 2. Copiar también dentro de subcarpeta Dashboard/ (compatibilidad retroactiva si alguien descomprime esperando Dashboard/)
Get-ChildItem -Path (Join-Path $projectRoot "Dashboard/app") -Exclude "__pycache__" | Copy-Item -Destination (Join-Path $tempDir "Dashboard/app/") -Recurse -Force
Copy-Item -Force (Join-Path $projectRoot "Dashboard/Dockerfile") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/docker-compose.yml") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/requirements.txt") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/.env.example") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/setup_proxmox_guide.md") (Join-Path $tempDir "Dashboard/")
Copy-Item -Force (Join-Path $projectRoot "Dashboard/README.md") (Join-Path $tempDir "Dashboard/")
Copy-Item -Recurse -Force (Join-Path $projectRoot "scripts/*") (Join-Path $tempDir "Dashboard/scripts/")

# Normalizar saltos de línea (CRLF a LF) en todos los scripts shell para evitar errores en Linux
Get-ChildItem -Path $tempDir -Filter "*.sh" -Recurse | ForEach-Object {
    $content = [System.IO.File]::ReadAllText($_.FullName)
    $normalized = $content.Replace("`r`n", "`n")
    [System.IO.File]::WriteAllText($_.FullName, $normalized, (New-Object System.Text.UTF8Encoding($false)))
}

# Comprimir a archivo zip
Compress-Archive -Path "$tempDir/*" -DestinationPath $outputZip -Force

# Generar archivo .tar.gz
if (Get-Command tar -ErrorAction SilentlyContinue) {
    tar -czf $outputTar -C $tempDir .
    Write-Host "Paquete TAR.GZ generado: $outputTar" -ForegroundColor Green
    
    # Copiar también alias offline
    $offlineTar = Join-Path $projectRoot "spotlight-proxmox-offline.tar.gz"
    Copy-Item $outputTar $offlineTar -Force
    Write-Host "Paquete Offline TAR.GZ: $offlineTar" -ForegroundColor Green
}

$offlineZip = Join-Path $projectRoot "spotlight-proxmox-offline.zip"
Copy-Item $outputZip $offlineZip -Force

# Limpiar directorio temporal
Remove-Item -Recurse -Force $tempDir

Write-Host "Paquete ZIP generado exitosamente: $outputZip" -ForegroundColor Green
Write-Host "Paquete Offline ZIP: $offlineZip" -ForegroundColor Green
