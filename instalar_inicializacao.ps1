# Configura o CtrlK Launcher para iniciar com o Windows.
# Metodo: Tarefa Agendada no logon, SEM atraso e com ALTA prioridade.
# Isso faz o app subir logo no inicio (nao por ultimo, como a pasta Inicializar).

$ErrorActionPreference = 'Stop'
$taskName = 'CtrlK Launcher'

# Pasta deste script = pasta do projeto
$workdir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script  = Join-Path $workdir 'ctrlk.py'

# Localiza o pythonw
$pyCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
    $py = $pyCmd.Source
} else {
    $py = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
}

$user = "$env:USERDOMAIN\$env:USERNAME"

Write-Host "Registrando tarefa de inicializacao..."

try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}

$action  = New-ScheduledTaskAction -Execute $py -Argument ('"' + $script + '" --tray') -WorkingDirectory $workdir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = 'PT0S'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable `
            -MultipleInstances IgnoreNew -Priority 1
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal `
        -Description 'Inicia o CtrlK Launcher ao logon, sem atraso, alta prioridade' -Force | Out-Null

    # Sucesso: remove o atalho da pasta Inicializar para nao abrir duas vezes
    $old = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\CtrlK Launcher.lnk"
    if (Test-Path $old) { Remove-Item $old -Force }

    Write-Host ""
    Write-Host "[OK] CtrlK vai iniciar com o Windows (logon, sem atraso, ALTA prioridade)."
    Write-Host "Estado da tarefa: $((Get-ScheduledTask -TaskName $taskName).State)"
}
catch {
    Write-Host ""
    Write-Host "[AVISO] Nao foi possivel criar a Tarefa Agendada:"
    Write-Host "        $($_.Exception.Message)"
    Write-Host "        Tente rodar este arquivo com BOTAO DIREITO > Executar como administrador."
    Write-Host "        (O atalho na pasta Inicializar continua funcionando como alternativa.)"
}

Write-Host ""
Write-Host "Pode fechar esta janela."
