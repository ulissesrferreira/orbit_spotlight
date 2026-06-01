$ErrorActionPreference = 'Stop'
$user     = $env:USERNAME
$explorer = Join-Path $env:WINDIR 'explorer.exe'

# Cria uma tarefa de logon SEM atraso (mesma velocidade do Search bar)
function New-LogonTask {
    param([string]$Name, [string]$Execute, [string]$Arg, [string]$WorkDir)

    if ([string]::IsNullOrEmpty($Arg)) {
        if ($WorkDir) { $action = New-ScheduledTaskAction -Execute $Execute -WorkingDirectory $WorkDir }
        else          { $action = New-ScheduledTaskAction -Execute $Execute }
    } else {
        if ($WorkDir) { $action = New-ScheduledTaskAction -Execute $Execute -Argument $Arg -WorkingDirectory $WorkDir }
        else          { $action = New-ScheduledTaskAction -Execute $Execute -Argument $Arg }
    }

    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $trigger.Delay = 'PT0S'
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
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
