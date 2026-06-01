# CtrlK Launcher

Launcher rápido para Windows — busca arquivos, pastas e apps com `Ctrl+'`.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15%2B-green?logo=qt&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)

## Como funciona

Pressione `Ctrl+'` em qualquer lugar para abrir o launcher. Digite para filtrar pastas, apps e arquivos instantaneamente. `Enter` abre o item selecionado, `ESC` fecha.

A tela inicial (sem digitação) mostra:
- Últimos 3 downloads
- Itens abertos recentemente via CtrlK
- Apps mais usados como fallback

A busca percorre Desktop, Documentos, Downloads, Imagens e OneDrive com até 5 níveis de profundidade, ordenando por recência e frequência de uso.

## Requisitos

- Windows 10/11
- Python 3.10+
- PyQt5

## Instalação

```bat
1_instalar.bat
```

Ou manualmente:

```sh
pip install -r requirements.txt
python ctrlk.py
```

Para iniciar com o Windows:

```bat
3_iniciar_com_windows.bat
```

## Scripts incluídos

| Script | O que faz |
|---|---|
| `1_instalar.bat` | Instala dependências |
| `2_executar.bat` | Executa o launcher |
| `3_iniciar_com_windows.bat` | Adiciona ao início automático |
| `4_gerenciar_inicializacao.bat` | Gerencia o início automático |

## Funcionalidades

- **Busca multi-token** — `"proj lp"` encontra itens que contenham ambas as palavras
- **Miniatura de imagens** — preview inline para `.jpg`, `.png`, `.webp`, `.gif`, `.svg`
- **Drag & drop** — arraste arquivos do launcher direto para outros apps
- **Integração Antigravity IDE** — botão para abrir pastas diretamente no IDE
- **Histórico de uso** — itens mais acessados sobem no ranking automaticamente
- **Tray icon** — roda em segundo plano, acessível pela bandeja do sistema

## Atalhos

| Tecla | Ação |
|---|---|
| `Ctrl+'` | Abrir / fechar |
| `↑` / `↓` | Navegar resultados |
| `Enter` | Abrir item selecionado |
| `ESC` | Fechar |
