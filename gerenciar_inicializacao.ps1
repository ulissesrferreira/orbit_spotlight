$ErrorActionPreference = 'Stop'
$user     = $env:USERNAME
$explorer = Join-Path $env:WINDIR 'explorer.exe'

# Cria uma tarefa de logon SEM atraso (mesma velocidade do Search bar)
function New-LogonTask {
    param([string]$Name, [string]$Execute, [string]$Arg, [string]$WorkDir)

    $userDomain = $env:USERDOMAIN
    $userName = $env:USERNAME
    $fullUser = "$userDomain\$userName"
    
    $executeEsc = [System.Security.SecurityElement]::Escape($Execute)
    $argumentsEsc = if ($Arg) { [System.Security.SecurityElement]::Escape($Arg) } else { "" }
    $workDirEsc = if ($WorkDir) { [System.Security.SecurityElement]::Escape($WorkDir) } else { "" }

    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Inicia o app $Name no logon, sem atraso e com prioridade.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$fullUser</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$fullUser</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$executeEsc</Command>
      $(if ($argumentsEsc) { "<Arguments>$argumentsEsc</Arguments>" })
      $(if ($workDirEsc) { "<WorkingDirectory>$workDirEsc</WorkingDirectory>" })
    </Exec>
  </Actions>
</Task>
"@

    $xmlPath = Join-Path $env:TEMP "Autostart_task_temp.xml"
    [System.IO.File]::WriteAllText($xmlPath, $xml, [System.Text.Encoding]::Unicode)
    
    & schtasks.exe /Create /TN $Name /XML "$xmlPath" /F | Out-Null
    
    Remove-Item $xmlPath -ErrorAction SilentlyContinue
}

function Show-List {
    $tasks = Get-ScheduledTask | Where-Object { $_.TaskName -like 'Autostart - *' -or $_.TaskName -eq 'Orbit Spotlight' } | Sort-Object TaskName
    if (-not $tasks) { Write-Host '   (nenhum)'; return }
    $i = 1
    foreach ($t in $tasks) { Write-Host ("   {0}. {1}   [{2}]" -f $i, $t.TaskName, $t.State); $i++ }
}

function Add-App {
    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title  = 'Selecione o atalho (.lnk) ou o programa (.exe) do app'
    $dlg.Filter = 'Apps e atalhos (*.lnk;*.exe)|*.lnk;*.exe|Todos os arquivos (*.*)|*.*'
    $dlg.InitialDirectory = [Environment]::GetFolderPath('Programs')
    if ($dlg.ShowDialog() -ne 'OK') { Write-Host 'Cancelado.'; return }

    $path = $dlg.FileName
    $base = [System.IO.Path]::GetFileNameWithoutExtension($path)
    $name = "Autostart - $base"
    $ext  = [System.IO.Path]::GetExtension($path).ToLower()

    if ($ext -eq '.lnk') {
        New-LogonTask -Name $name -Execute $explorer -Arg ('"' + $path + '"')
    } else {
        New-LogonTask -Name $name -Execute $path -WorkDir (Split-Path $path)
    }
    Write-Host ""
    Write-Host "[OK] '$base' vai iniciar com o Windows." -ForegroundColor Green
}

function Remove-App {
    $tasks = @(Get-ScheduledTask | Where-Object { $_.TaskName -like 'Autostart - *' } | Sort-Object TaskName)
    if ($tasks.Count -eq 0) { Write-Host 'Nenhum app de autostart para remover.'; return }
    Write-Host ''
    $i = 1
    foreach ($t in $tasks) { Write-Host ("   {0}. {1}" -f $i, $t.TaskName); $i++ }
    Write-Host ''
    $sel = Read-Host 'Numero do app para remover (Enter para cancelar)'
    if ([string]::IsNullOrWhiteSpace($sel)) { return }
    $idx = 0
    if ([int]::TryParse($sel, [ref]$idx) -and $idx -ge 1 -and $idx -le $tasks.Count) {
        $t = $tasks[$idx - 1]
        Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false
        Write-Host ""
        Write-Host "[OK] Removido: $($t.TaskName)" -ForegroundColor Yellow
    } else {
        Write-Host 'Selecao invalida.' -ForegroundColor Red
    }
}

while ($true) {
    Write-Host ''
    Write-Host '================================================='
    Write-Host '    Apps que iniciam com o Windows (rapido)'
    Write-Host '================================================='
    Show-List
    Write-Host ''
    Write-Host '   [A] Adicionar app     [R] Remover app     [S] Sair'
    $op = (Read-Host 'Escolha').ToUpper()
    if ($op -eq 'S') { break }
    switch ($op) {
        'A'     { Add-App }
        'R'     { Remove-App }
        default { Write-Host 'Opcao invalida.' -ForegroundColor Red }
    }
}
