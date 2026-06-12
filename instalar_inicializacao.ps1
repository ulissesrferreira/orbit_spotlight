# Configura o Orbit Spotlight para iniciar com o Windows.
# Metodo: Tarefa Agendada no logon, SEM atraso e com ALTA prioridade.
# Isso faz o app subir logo no inicio (nao por ultimo, como a pasta Inicializar).

$ErrorActionPreference = 'Stop'
$taskName = 'Orbit Spotlight'

# Pasta deste script = pasta do projeto
$workdir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script  = Join-Path $workdir 'orbit_spotlight.py'

# Localiza o pythonw
$pyCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($pyCmd) {
    $py = $pyCmd.Source
} else {
    $py = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
}

$user = "$env:USERDOMAIN\$env:USERNAME"

Write-Host "Registrando tarefa de inicializacao..."

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Inicia o Orbit Spotlight no logon, sem atraso e com prioridade.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$user</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$user</UserId>
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
      <Command>$py</Command>
      <Arguments>"$script" --tray</Arguments>
      <WorkingDirectory>$workdir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

try {
    $xmlPath = Join-Path $env:TEMP "OrbitSpotlight_task.xml"
    [System.IO.File]::WriteAllText($xmlPath, $xml, [System.Text.Encoding]::Unicode)
    
    # Executa o schtasks para criar a tarefa importando o XML
    & schtasks.exe /Create /TN $taskName /XML "$xmlPath" /F | Out-Null
    
    # Limpa o arquivo temporario
    Remove-Item $xmlPath -ErrorAction SilentlyContinue

    # Sucesso: remove o atalho da pasta Inicializar para nao abrir duas vezes
    $old = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Orbit Spotlight.lnk"
    if (Test-Path $old) { Remove-Item $old -Force }

    Write-Host ""
    Write-Host "[OK] Orbit Spotlight vai iniciar com o Windows (logon, sem atraso, ALTA prioridade)."
    Write-Host "Estado da tarefa: $((Get-ScheduledTask -TaskName $taskName).State)"
}
catch {
    Write-Host ""
    Write-Host "[AVISO] Nao foi possivel criar a Tarefa Agendada:"
    Write-Host "        $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Pode fechar esta janela."
