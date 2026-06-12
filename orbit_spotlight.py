#!/usr/bin/env python3
"""
Orbit Spotlight — Quick file, folder & app search for Windows
Press Ctrl+apostrophe anywhere to open/close the launcher.
"""

import sys
import os
import json
import time
import logging
import subprocess
import ctypes
import ctypes.wintypes
import threading
from pathlib import Path
import keyboard

from PyQt5.QtWidgets import (
    QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QScrollArea, QSystemTrayIcon, QMenu, QAction,
    QGraphicsDropShadowEffect, QShortcut, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QEvent, QObject, QAbstractNativeEventFilter, QMimeData, QUrl, QPoint, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush, QPen, QPainterPath, QImageReader, QKeySequence, QDrag, QCursor

# ─────────────────────────────────────────────
# Prioridade do processo
# ─────────────────────────────────────────────
def set_high_priority():
    """Eleva a prioridade do processo no Windows para resposta mais rápida."""
    try:
        HIGH_PRIORITY_CLASS = 0x00000080
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.SetPriorityClass.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        kernel32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
# Hotkey global ABNT2 usando biblioteca keyboard
# Classes de navegadores conhecidas
_BROWSER_CLASSES = {
    "Chrome_WidgetWin_1",     # Chrome / Brave / Edge / Opera
    "MozillaWindowClass",     # Firefox
    "ApplicationFrameWindow", # alguns browsers UWP
    "IEFrame",                # Internet Explorer
}

# Only these file types will appear in results
ALLOWED_EXTENSIONS = {
    # imagens
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".ico", ".tiff",
    # documentos
    ".txt", ".md", ".pdf", ".csv", ".rtf",
    # web / markup
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".xml", ".yaml", ".yml",
    # dados / config
    ".json", ".toml", ".ini", ".env", ".conf", ".cfg", ".lock",
    # código
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".kts", ".swift", ".go", ".rs", ".rb", ".php",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".dart", ".lua", ".sh", ".bat", ".ps1",
    ".r", ".sql", ".graphql", ".proto",
    # notebooks / data
    ".ipynb",
    # office / docs
    ".docx", ".xlsx", ".pptx", ".odt", ".ods",
    # fontes
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # misc dev
    ".gitignore", ".editorconfig", ".dockerfile",
}

# Tipos que ganham miniatura (preview) ao inves do emoji
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"}

# File where we track app usage counts
USAGE_FILE = Path(os.environ.get("APPDATA", "")) / "OrbitSpotlight" / "usage.json"

# ─────────────────────────────────────────────
# Logging estruturado (arquivo em %APPDATA%/OrbitSpotlight/orbit.log)
# ─────────────────────────────────────────────
LOG_FILE = USAGE_FILE.parent / "orbit.log"

def _setup_logging() -> logging.Logger:
    logger = logging.getLogger("orbit")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            h = logging.FileHandler(LOG_FILE, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(h)
        except Exception:
            logger.addHandler(logging.NullHandler())
    return logger

log = _setup_logging()

FILE_ICONS = {
    # imagens
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".webp": "🖼️",
    ".gif": "🖼️", ".svg": "🖼️", ".bmp": "🖼️", ".ico": "🖼️", ".tiff": "🖼️",
    # documentos
    ".pdf": "📕", ".md": "📝", ".txt": "📃", ".csv": "📊", ".rtf": "📃",
    # web
    ".html": "🌐", ".htm": "🌐", ".css": "🎨", ".scss": "🎨", ".sass": "🎨",
    ".less": "🎨", ".xml": "📋",
    # dados / config
    ".json": "📋", ".yaml": "📋", ".yml": "📋", ".toml": "📋",
    ".ini": "⚙️", ".env": "⚙️", ".conf": "⚙️", ".cfg": "⚙️", ".lock": "🔒",
    # código
    ".py": "🐍", ".js": "🟨", ".ts": "🔷", ".jsx": "⚛️", ".tsx": "⚛️",
    ".mjs": "🟨", ".cjs": "🟨",
    ".java": "☕", ".kt": "🟣", ".kts": "🟣", ".swift": "🟠",
    ".go": "🐹", ".rs": "🦀", ".rb": "💎", ".php": "🐘",
    ".c": "🔵", ".cpp": "🔵", ".h": "🔵", ".hpp": "🔵",
    ".cs": "🟦", ".dart": "🎯", ".lua": "🌙",
    ".sh": "🖥️", ".bat": "🖥️", ".ps1": "🖥️",
    ".r": "📊", ".sql": "🗄️", ".graphql": "📋", ".proto": "📋",
    # notebooks
    ".ipynb": "📓",
    # office
    ".docx": "📄", ".xlsx": "📊", ".pptx": "📊", ".odt": "📄", ".ods": "📊",
    # fontes
    ".ttf": "🔤", ".otf": "🔤", ".woff": "🔤", ".woff2": "🔤", ".eot": "🔤",
    # misc
    ".gitignore": "⚙️", ".editorconfig": "⚙️", ".dockerfile": "🐳",
}


# ─────────────────────────────────────────────
# Integração com o Antigravity IDE
# ─────────────────────────────────────────────
def _find_antigravity_exe() -> str | None:
    """Localiza o executável do Antigravity IDE instalado, ou None."""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    pf    = Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
    candidates = [
        local / "Programs" / "Antigravity"     / "Antigravity IDE.exe",
        local / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe",
        pf    / "Antigravity"                  / "Antigravity IDE.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None

ANTIGRAVITY_EXE = _find_antigravity_exe()

def _antigravity_icon_path() -> str | None:
    """Caminho do logo do Antigravity (usado no botão), ou None."""
    if not ANTIGRAVITY_EXE:
        return None
    ico = (Path(ANTIGRAVITY_EXE).parent
           / "resources" / "app" / "resources" / "win32" / "code_70x70.png")
    return str(ico) if ico.exists() else None

ANTIGRAVITY_ICON = _antigravity_icon_path()

def _antigravity_cli_path() -> str | None:
    """Caminho do cli.js do Antigravity (CLI oficial, igual antigravity-ide.cmd)."""
    if not ANTIGRAVITY_EXE:
        return None
    cli = Path(ANTIGRAVITY_EXE).parent / "resources" / "app" / "out" / "cli.js"
    return str(cli) if cli.exists() else None

ANTIGRAVITY_CLI = _antigravity_cli_path()

# Flag do Windows: não abre janela de console ao lançar via subprocess
_CREATE_NO_WINDOW = 0x08000000

def open_in_antigravity(path: str) -> bool:
    """Abre a pasta/arquivo no Antigravity IDE. Retorna True se iniciou.

    Usa o CLI oficial (cli.js com ELECTRON_RUN_AS_NODE=1) — o mesmo que o
    `antigravity-ide.cmd` faz. É o caminho que conversa com a instância em
    execução, abre a pasta e TRAZ a janela pra frente de forma confiável.
    Lançar o .exe direto às vezes abre em segundo plano (parecia "não abrir").
    """
    if not ANTIGRAVITY_EXE:
        log.error("open_in_antigravity: ANTIGRAVITY_EXE nao encontrado")
        return False
    try:
        if ANTIGRAVITY_CLI:
            env = os.environ.copy()
            env["ELECTRON_RUN_AS_NODE"] = "1"
            log.info("open_in_antigravity: CLI cli.js path=%r", path)
            subprocess.Popen([ANTIGRAVITY_EXE, ANTIGRAVITY_CLI, path],
                             env=env, creationflags=_CREATE_NO_WINDOW)
        else:
            log.info("open_in_antigravity: fallback exe direto path=%r", path)
            subprocess.Popen([ANTIGRAVITY_EXE, path])
        return True
    except Exception as e:
        log.exception("open_in_antigravity: falhou")
        print(f"[OrbitSpotlight] Erro ao abrir no Antigravity: {e}")
        return False


# ─────────────────────────────────────────────
# Usage tracker (persisted per-app click count)
# ─────────────────────────────────────────────
def load_usage() -> dict:
    try:
        if USAGE_FILE.exists():
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_usage(data: dict):
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def record_usage(path: str):
    """Incrementa contagem e registra timestamp do ultimo acesso."""
    data = load_usage()
    data[path] = data.get(path, 0) + 1
    last = data.setdefault("_last", {})
    last[path] = time.time()
    save_usage(data)


# ─────────────────────────────────────────────
# Background search worker
# ─────────────────────────────────────────────
class SearchWorker(QThread):
    results_ready = pyqtSignal(list)

    # Detecta OneDrive sincronizado (Desktop/Documentos podem estar lá)
    _home = Path.home()
    _onedrive = next(
        (p for p in [_home / "OneDrive", _home / "OneDrive - Personal"] if p.exists()),
        None
    )
    # Pasta de fontes do usuário (Local AppData) e do sistema
    _local_appdata = Path(os.environ.get("LOCALAPPDATA", str(_home / "AppData" / "Local")))
    _user_fonts = _local_appdata / "Microsoft" / "Windows" / "Fonts"
    _system_fonts = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "Fonts"

    SEARCH_DIRS = [d for d in [
        _home / "Desktop",
        (_onedrive / "\u00c1rea de Trabalho") if _onedrive else None,
        (_onedrive / "Desktop")                if _onedrive else None,
        _home / "Documents",
        (_onedrive / "Documentos")             if _onedrive else None,
        (_onedrive / "Documents")              if _onedrive else None,
        _home / "Downloads",
        _home / "Pictures",
        _onedrive                              if _onedrive else None,
        _user_fonts,
        _system_fonts,
        _home,
    ] if d is not None and Path(d).exists()]

    # Pastas do sistema excluídas da busca
    EXCLUDED_DIRS: set = {
        str(p).lower() for p in [
            _home / "AppData",
            _home / "anaconda3",
            _home / ".conda",
            _home / "miniconda3",
        ] if p.exists()
    }

    START_MENU_DIRS = [
        Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]

    def __init__(self, query: str):
        super().__init__()
        self.query = query
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @staticmethod
    def _matches(name_lower: str, tokens: list[str],
                 path_lower: str = "", is_path_query: bool = False) -> bool:
        if is_path_query and path_lower:
            normalized = path_lower.replace("\\", "/")
            fragment = " ".join(tokens).replace("\\", "/").lstrip("/")
            return fragment in normalized
        return all(t in name_lower for t in tokens)

    @staticmethod
    def _match_score(name_lower: str, tokens: list[str]) -> int:
        """0 = começa com primeiro token, 1 = contém."""
        if name_lower.startswith(tokens[0]):
            return 0
        return 1

    def run(self):
        if not self.query.strip():
            self.results_ready.emit(self._get_home_screen())
        else:
            results = self._search(self.query.lower().strip())
            if not self._cancelled:
                self.results_ready.emit(results)

    # ── Home screen (no query typed) ──────────
    def _get_home_screen(self):
        _hdata   = load_usage()
        usage    = {k: v for k, v in _hdata.items() if k != "_last"}
        last_map = _hdata.get("_last", {})
        results  = []
        seen     = set()

        # 1. Últimos 3 downloads (qualquer tipo de arquivo), sempre no topo
        downloads = Path.home() / "Downloads"
        if downloads.exists():
            dl_files = []
            try:
                for f in downloads.iterdir():
                    if f.is_file():
                        dl_files.append(f)
            except PermissionError:
                pass
            dl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for f in dl_files[:3]:
                seen.add(str(f))
                results.append({"name": f.name, "path": str(f), "type": "file",
                                 "icon": FILE_ICONS.get(f.suffix.lower(), "📄"),
                                 "subtitle": "Download recente"})

        # 2. Itens abertos recentemente via ctrlk (qualquer tipo), ordem por timestamp
        for path, ts in sorted(last_map.items(), key=lambda x: -x[1]):
            p = Path(path)
            try:
                exists = p.exists()
            except OSError:
                continue
            if not exists or path in seen:
                continue
            seen.add(path)
            if p.suffix.lower() == ".lnk":
                results.append({"name": p.stem, "path": path, "type": "app",
                                 "icon": "⚡", "subtitle": "Aplicativo"})
            elif p.is_dir():
                results.append({"name": p.name, "path": path, "type": "folder",
                                 "icon": "📁", "subtitle": str(p.parent)})
            elif p.suffix.lower() in ALLOWED_EXTENSIONS:
                results.append({"name": p.name, "path": path, "type": "file",
                                 "icon": FILE_ICONS.get(p.suffix.lower(), "📄"),
                                 "subtitle": str(p.parent)})
            if len(results) >= 11:
                break

        # 3. Apps mais usados como fallback (preenche se lista ainda vazia)
        if len(results) < 4:
            all_apps = self._collect_all_apps()
            all_apps.sort(key=lambda a: (-last_map.get(a["path"], 0),
                                         -usage.get(a["path"], 0), a["name"].lower()))
            for app in all_apps:
                if app["path"] not in seen:
                    results.append(app)
                    seen.add(app["path"])
                if len(results) >= 6:
                    break

        return results

    def _collect_all_apps(self) -> list:
        apps = {}
        for start_dir in self.START_MENU_DIRS:
            if not start_dir.exists():
                continue
            for lnk in start_dir.rglob("*.lnk"):
                if lnk.stem not in apps:
                    apps[lnk.stem] = {
                        "name": lnk.stem,
                        "path": str(lnk),
                        "type": "app",
                        "icon": "⚡",
                        "subtitle": "Aplicativo",
                    }
        return list(apps.values())

    # ── Search ────────────────────────────────────────
    def _search(self, query: str) -> list:
        _data  = load_usage()
        usage  = {k: v for k, v in _data.items() if k != "_last"}
        last   = _data.get("_last", {})
        folders, files, apps = [], [], []
        seen: set = set()
        tokens = query.split()
        is_path_query = any(sep in query for sep in ("/", "\\"))

        # Suporte para caminhos absolutos diretos colados pelo usuário
        try:
            expanded_query = os.path.expandvars(query)
            query_path = Path(expanded_query)
            if query_path.is_absolute() and query_path.exists():
                key = str(query_path.resolve())
                if key not in seen:
                    seen.add(key)
                    if query_path.is_dir():
                        folders.append({
                            "name": query_path.name,
                            "path": key,
                            "type": "folder",
                            "icon": "📁",
                            "subtitle": str(query_path.parent),
                        })
                    else:
                        suffix = query_path.suffix.lower()
                        files.append({
                            "name": query_path.name,
                            "path": key,
                            "type": "file",
                            "icon": FILE_ICONS.get(suffix, "📄"),
                            "subtitle": str(query_path.parent),
                        })
        except Exception:
            pass

        # 0. As proprias pastas-base sao candidatas (ex: "Downloads", "Documentos")
        for base in self.SEARCH_DIRS:
            if self._matches(base.name.lower(), tokens, str(base).lower(), is_path_query):
                key = str(base)
                if key not in seen:
                    seen.add(key)
                    folders.append({
                        "name": base.name,
                        "path": key,
                        "type": "folder",
                        "icon": "📁",
                        "subtitle": str(base.parent),
                    })

        # 1. Pastas e arquivos via iterdir recursivo
        for base in self.SEARCH_DIRS:
            if self._cancelled:
                break
            self._collect_from(base, tokens, folders, files, seen,
                                depth=0, max_depth=5, is_path_query=is_path_query)
            if len(folders) >= 12 and len(files) >= 8:
                break

        # 2. Apps
        for app in self._collect_all_apps():
            if self._cancelled:
                break
            if self._matches(app["name"].lower(), tokens) and app["path"] not in seen:
                seen.add(app["path"])
                apps.append(app)
            if len(apps) >= 8:
                break

        def sort_key(r):
            # 1) comeca com primeiro token; 2) recencia; 3) uso desc; 4) alfa
            starts = self._match_score(r["name"].lower(), tokens)
            ts     = last.get(r["path"], 0)
            if ts == 0 and r["type"] == "file":
                try:
                    ts = Path(r["path"]).stat().st_mtime
                except OSError:
                    ts = 0
            count  = usage.get(r["path"], 0)
            return (starts, -ts, -count, r["name"].lower())

        folders.sort(key=sort_key)
        files.sort(key=sort_key)
        apps.sort(key=sort_key)

        return (folders[:8] + files[:8] + apps[:8])[:20]

    def _collect_from(self, path: Path, tokens: list[str],
                      folders: list, files: list, seen: set,
                      depth: int, max_depth: int, is_path_query: bool = False):
        """Busca recursiva usando iterdir — mais confiável com OneDrive."""
        if depth > max_depth or self._is_excluded(path):
            return
        if len(folders) >= 12 and len(files) >= 8:
            return
        try:
            for item in path.iterdir():
                if self._cancelled:
                    return
                key = str(item)
                if key in seen:
                    continue
                try:
                    is_dir = item.is_dir()
                except OSError:
                    continue

                if self._matches(item.name.lower(), tokens, key.lower(), is_path_query):
                    seen.add(key)
                    if is_dir:
                        folders.append({
                            "name": item.name,
                            "path": key,
                            "type": "folder",
                            "icon": "📁",
                            "subtitle": str(item.parent),
                        })
                    elif item.suffix.lower() in ALLOWED_EXTENSIONS:
                        files.append({
                            "name": item.name,
                            "path": key,
                            "type": "file",
                            "icon": FILE_ICONS.get(item.suffix.lower(), "📄"),
                            "subtitle": str(item.parent),
                        })

                if is_dir and depth < max_depth and not self._is_excluded(item):
                    self._collect_from(item, tokens, folders, files, seen,
                                       depth + 1, max_depth, is_path_query)
        except PermissionError:
            pass

    # Nomes de pastas ignoradas em qualquer nivel da arvore
    EXCLUDED_NAMES = {
        "node_modules", ".git", ".svn", "__pycache__",
        "venv", ".venv", "dist", ".next", ".nuxt",
    }

    def _is_excluded(self, path: Path) -> bool:
        p = str(path).lower()
        # Não excluir a pasta de fontes do usuário (que fica dentro do AppData)
        user_fonts = str(self._user_fonts).lower()
        if p == user_fonts or p.startswith(user_fonts + os.sep):
            return False
        if any(p == ex or p.startswith(ex + os.sep) for ex in self.EXCLUDED_DIRS):
            return True
        return path.name.lower() in self.EXCLUDED_NAMES




# ─────────────────────────────────────────────
# Single result row widget
# ─────────────────────────────────────────────
_AG_ICON_CACHE: dict = {}

def _get_antigravity_qicon():
    """QIcon do logo do Antigravity (carregado uma vez), ou None."""
    if not ANTIGRAVITY_ICON:
        return None
    if "icon" not in _AG_ICON_CACHE:
        pm = QPixmap(ANTIGRAVITY_ICON)
        _AG_ICON_CACHE["icon"] = QIcon(pm) if not pm.isNull() else None
    return _AG_ICON_CACHE["icon"]


class ResultRow(QFrame):
    clicked = pyqtSignal()
    open_antigravity = pyqtSignal()

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self._selected = False
        self._drag_start: QPoint | None = None
        self._dragging = False
        self._build()

    def _build(self):
        self.setFixedHeight(50)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 14, 6)
        layout.setSpacing(10)

        icon = QLabel()
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignCenter)
        thumb = self._load_thumbnail()
        if thumb is not None:
            icon.setPixmap(thumb)
            icon.setStyleSheet("background: transparent;")
        else:
            icon.setText(self.result.get("icon", "📄"))
            icon.setStyleSheet("font-size: 17px; background: transparent;")
        layout.addWidget(icon)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)

        name = QLabel(self.result["name"])
        name.setStyleSheet("color: #e2e2e2; font-size: 13px; font-weight: 600; background: transparent;")
        name.setWordWrap(False)

        sub = self.result.get("subtitle", self.result.get("path", ""))
        if len(sub) > 72:
            sub = "…" + sub[-70:]
        subtitle = QLabel(sub)
        subtitle.setStyleSheet("color: #666; font-size: 11px; background: transparent;")

        text_box.addWidget(name)
        text_box.addWidget(subtitle)
        layout.addLayout(text_box, 1)

        # Botão "Abrir no Antigravity" — só para pastas
        if self.result.get("type") == "folder" and ANTIGRAVITY_EXE:
            self._add_antigravity_button(layout)

        self._update_bg()

    def _add_antigravity_button(self, layout):
        btn = QPushButton()
        btn.setFixedSize(30, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Abrir no Antigravity")
        btn.setFocusPolicy(Qt.NoFocus)
        icon = _get_antigravity_qicon()
        if icon is not None:
            btn.setIcon(icon)
            btn.setIconSize(QSize(18, 18))
        else:
            btn.setText("AG")
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid #2c2c2c;
                border-radius: 7px;
                color: #cfcfcf;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.10);
                border: 1px solid #3d6da8;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.16);
            }
        """)
        btn.clicked.connect(self.open_antigravity.emit)
        layout.addWidget(btn)

    def _load_thumbnail(self):
        """Retorna um QPixmap miniatura para arquivos de imagem, ou None."""
        if self.result.get("type") != "file":
            return None
        path = self.result.get("path", "")
        ext = os.path.splitext(path)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            return None
        try:
            target = 28
            reader = QImageReader(path)
            reader.setAutoTransform(True)  # respeita orientacao EXIF
            size = reader.size()
            if size.isValid() and (size.width() > target or size.height() > target):
                w, h = size.width(), size.height()
                if w >= h:
                    nw, nh = target, max(1, round(h * target / w))
                else:
                    nw, nh = max(1, round(w * target / h)), target
                reader.setScaledSize(QSize(nw, nh))  # decodifica ja reduzido
            img = reader.read()
            if img.isNull():
                return None
            return self._rounded(QPixmap.fromImage(img), 5)
        except Exception:
            return None

    @staticmethod
    def _rounded(pm: QPixmap, radius: int) -> QPixmap:
        """Aplica cantos arredondados na miniatura."""
        size = pm.size()
        rounded = QPixmap(size)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, pm)
        painter.end()
        return rounded

    def set_selected(self, val: bool):
        if self._selected != val:
            self._selected = val
            self._update_bg()

    def _update_bg(self):
        self.setStyleSheet(
            "QFrame { background-color: #1f3a5f; border-radius: 7px; }"
            if self._selected else
            "QFrame { background-color: transparent; border-radius: 7px; }"
            "QFrame:hover { background-color: #222; }"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self._dragging = False

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return
        path = self.result.get("path", "")
        if not path or self.result.get("type") not in ("file",):
            return
        self._dragging = True
        # Pausa o poll de foco para não fechar a janela durante o drag
        launcher = self._find_launcher()
        if launcher:
            launcher._focus_poll.stop()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)
        # Retoma o poll após o drag terminar (com margem de segurança)
        if launcher:
            QTimer.singleShot(300, launcher._focus_poll.start)

    def _find_launcher(self):
        """Sobe a hierarquia de widgets para encontrar o Launcher."""
        p = self.parent()
        while p is not None:
            if isinstance(p, Launcher):
                return p
            p = p.parent()
        return None

    def mouseReleaseEvent(self, event):
        # Só abre se foi um clique simples (sem arraste)
        if event.button() == Qt.LeftButton and not self._dragging:
            self.clicked.emit()
        self._drag_start = None
        self._dragging = False


# ─────────────────────────────────────────────
# Main launcher window
# ─────────────────────────────────────────────
class Launcher(QWidget):
    _show_signal   = pyqtSignal()
    _hide_signal   = pyqtSignal()
    _toggle_signal = pyqtSignal()

    _VK_MENU = 0x12  # Virtual key code do Alt no Windows

    def __init__(self):
        super().__init__()
        self._results: list = []
        self._rows: list = []
        self._sel: int = -1
        self._worker = None
        self._alt_was_down = False

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._start_search)

        self._show_signal.connect(self._do_show)
        self._hide_signal.connect(self.hide)
        self._toggle_signal.connect(self._toggle)

        self._build_ui()

        # ESC fecha de qualquer widget da aplicacao
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.ApplicationShortcut)
        esc.activated.connect(self._on_esc)

        # Timer para detectar perda de foco (clique fora)
        self._focus_poll = QTimer(self)
        self._focus_poll.setInterval(150)
        self._focus_poll.timeout.connect(self._check_focus)

        # Polling do Alt via GetAsyncKeyState (mais confiável que hooks no Windows)
        self._alt_poll = QTimer(self)
        self._alt_poll.setInterval(50)
        self._alt_poll.timeout.connect(self._check_alt_state)

    # ── UI ────────────────────────────────────
    def _build_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 20)

        self._card = QFrame()
        self._card.setObjectName("card")
        self._card.setStyleSheet("""
            QFrame#card {
                background-color: #141414;
                border-radius: 14px;
                border: 1px solid #2a2a2a;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 10)
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 10)
        card_layout.setSpacing(0)

        # ── Search row
        search_row = QHBoxLayout()
        search_row.setContentsMargins(16, 14, 16, 10)
        search_row.setSpacing(10)

        lupa = QLabel("⌕")
        lupa.setStyleSheet("color: #555; font-size: 20px; background: transparent;")
        lupa.setFixedWidth(22)
        search_row.addWidget(lupa)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Buscar pastas, apps, arquivos…")
        self._input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ebebeb;
                font-size: 16px;
                font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;
                padding: 2px 0;
            }
        """)
        self._input.textChanged.connect(self._on_text)
        self._input.installEventFilter(self)
        search_row.addWidget(self._input)

        hint = QLabel("ESC · ↑↓ · ↵ abrir")
        hint.setStyleSheet("color: #363636; font-size: 11px; font-family: 'Segoe UI'; background: transparent;")
        search_row.addWidget(hint)

        card_layout.addLayout(search_row)

        # ── Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #222; margin: 0 10px;")
        card_layout.addWidget(div)

        # ── Results scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 5px; margin: 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #2e2e2e; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(8, 6, 8, 2)
        self._list_layout.setSpacing(2)

        self._scroll.setWidget(self._list_container)
        card_layout.addWidget(self._scroll)

        # ── Empty/status label
        self._status = QLabel("Nenhum resultado encontrado")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(
            "color: #3a3a3a; font-size: 13px; padding: 18px; background: transparent;"
        )
        card_layout.addWidget(self._status)

        outer.addWidget(self._card)
        self._set_height(0)

    def _set_height(self, n_results: int):
        OUTER_V     = 36
        CARD_BOTTOM = 10
        SEARCH_ROW  = 54
        DIVIDER     = 2
        ITEM_H      = 52
        LIST_PAD    = 8
        STATUS_H    = 58

        visible = min(n_results, 7)

        if visible == 0:
            content_h = SEARCH_ROW + DIVIDER + STATUS_H + CARD_BOTTOM
        else:
            scroll_h = visible * ITEM_H + LIST_PAD
            self._scroll.setFixedHeight(scroll_h)
            content_h = SEARCH_ROW + DIVIDER + scroll_h + CARD_BOTTOM

        self.setFixedHeight(OUTER_V + content_h)

    def _toggle(self):
        if self.isVisible():
            self._hide_signal.emit()
        else:
            self._show_signal.emit()

    # ── Show / hide ───────────────────────────
    def _do_show(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            int(screen.height() * 0.22),
        )
        self.show()
        self.raise_()
        self.activateWindow()

        # Força foreground via AttachThreadInput (burla restricao do Windows)
        hwnd       = int(self.winId())
        fg_hwnd    = ctypes.windll.user32.GetForegroundWindow()
        fg_tid     = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)
        cur_tid    = ctypes.windll.kernel32.GetCurrentThreadId()
        if fg_tid != cur_tid:
            ctypes.windll.user32.AttachThreadInput(fg_tid, cur_tid, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.BringWindowToTop(hwnd)
        if fg_tid != cur_tid:
            ctypes.windll.user32.AttachThreadInput(fg_tid, cur_tid, False)


        # Limpa e foca automaticamente no input
        self._input.clear()

        # Focus imediato
        self._input.setFocus(Qt.ActiveWindowFocusReason)

        # Focus reforçado (Windows às vezes rouba o foco)
        QTimer.singleShot(0, self._input.setFocus)
        QTimer.singleShot(50, self._input.setFocus)
        QTimer.singleShot(120, self._input.setFocus)

        self._fire_search("")
        self._alt_was_down = False
        log.info("do_show: janela exibida; polls (foco+alt) agendados em 400ms")
        # Adia os polls para depois dos timers de foco (0, 50, 120 ms) terem disparado
        QTimer.singleShot(400, self._focus_poll.start)
        QTimer.singleShot(400, self._alt_poll.start)

    # ── Search ────────────────────────────────
    def _on_text(self, text):
        self._debounce.stop()
        self._debounce.start(120)

    def _start_search(self):
        self._fire_search(self._input.text())

    def _fire_search(self, query: str):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
        self._worker = SearchWorker(query)
        self._worker.results_ready.connect(self._on_results)
        self._worker.start()

    def _on_results(self, results: list):
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()
        self._results = results

        if not results:
            self._scroll.hide()
            self._status.show()
            self._set_height(0)
            self._sel = -1
            return

        self._status.hide()
        self._scroll.show()
        self._sel = 0

        for i, r in enumerate(results):
            row = ResultRow(r)
            row.set_selected(i == 0)
            idx = i
            row.clicked.connect(lambda _idx=idx: self._open(_idx))
            row.open_antigravity.connect(lambda _idx=idx: self._open_antigravity(_idx))
            self._list_layout.addWidget(row)
            self._rows.append(row)

        self._set_height(len(results))

    # ── Keyboard ─────────────────────────────────────────────────────
    def _on_esc(self):
        if self.isVisible():
            self.hide()

    def _check_focus(self):
        if self.isVisible() and not self.isActiveWindow():
            if ctypes.windll.user32.GetAsyncKeyState(self._VK_MENU) & 0x8000:
                return
            log.info("check_focus: escondendo (perdeu foco)")
            self.hide()

    def eventFilter(self, obj: QObject, event: QEvent):
        if obj is self._input and event.type() == QEvent.KeyPress:
            k = event.key()
            if k == Qt.Key_Down:
                self._move_sel(1)
                return True
            if k == Qt.Key_Up:
                self._move_sel(-1)
                return True
            if k in (Qt.Key_Return, Qt.Key_Enter):
                self._open(self._sel)
                return True
        return super().eventFilter(obj, event)

    def _check_alt_state(self):
        """Polling de 50ms via GetAsyncKeyState — detecta Alt com borda de subida."""
        pressed = bool(ctypes.windll.user32.GetAsyncKeyState(self._VK_MENU) & 0x8000)
        if pressed != self._alt_was_down:
            log.debug("alt poll: estado -> %s (visivel=%s, ativa=%s)",
                      pressed, self.isVisible(), self.isActiveWindow())
        if pressed and not self._alt_was_down:
            self._on_alt_key()
        self._alt_was_down = pressed

    def _on_alt_key(self):
        """Abre no Antigravity a pasta sob o cursor quando Alt é pressionado.

        Usa hit-test geométrico (QCursor.pos) em vez de underMouse(): este é
        furado quando a linha tem widgets-filhos (os QLabels de nome/subtítulo
        cobrem quase toda a largura), retornando False sobre o texto.
        """
        pos = QCursor.pos()
        log.info("on_alt_key: cursor=(%d,%d) rows=%d results=%d",
                 pos.x(), pos.y(), len(self._rows), len(self._results))
        for i, row in enumerate(self._rows):
            if i >= len(self._results):
                break
            rtype = self._results[i].get("type")
            inside = row.isVisible() and row.rect().contains(row.mapFromGlobal(pos))
            log.debug("  row %d type=%s visivel=%s dentro=%s", i, rtype, row.isVisible(), inside)
            if rtype != "folder":
                continue
            if inside:
                log.info("on_alt_key: MATCH pasta idx=%d path=%s",
                         i, self._results[i].get("path"))
                self._open_antigravity(i)
                return
        log.info("on_alt_key: nenhuma pasta sob o cursor")

    def _move_sel(self, delta: int):
        if not self._rows:
            return
        if 0 <= self._sel < len(self._rows):
            self._rows[self._sel].set_selected(False)
        self._sel = max(0, min(self._sel + delta, len(self._rows) - 1))
        self._rows[self._sel].set_selected(True)
        self._scroll.ensureWidgetVisible(self._rows[self._sel])

    # ── Open ─────────────────────────────────
    def _open(self, idx: int):
        if not (0 <= idx < len(self._results)):
            return
        result = self._results[idx]
        path = result["path"]
        record_usage(path)  # track usage for folders, files and apps alike
        try:
            os.startfile(path)
        except Exception:
            try:
                subprocess.Popen(["explorer", path])
            except Exception as e:
                print(f"[OrbitSpotlight] Erro ao abrir: {e}")
        self.hide()

    def _open_antigravity(self, idx: int):
        """Abre a pasta selecionada no Antigravity IDE (botão da linha)."""
        if not (0 <= idx < len(self._results)):
            log.warning("_open_antigravity: idx %d fora do intervalo", idx)
            return
        path = self._results[idx]["path"]
        log.info("_open_antigravity: idx=%d path=%s", idx, path)
        record_usage(path)
        ok = open_in_antigravity(path)
        log.info("_open_antigravity: resultado=%s", ok)
        self.hide()

    def hide(self):
        self._focus_poll.stop()
        self._alt_poll.stop()
        super().hide()

    def closeEvent(self, event):
        keyboard.unhook_all_hotkeys()
        # Limpa o RegisterHotKey do Win32 (se registrado)
        try:
            ctypes.windll.user32.UnregisterHotKey(None, 0x0001)
        except Exception:
            pass
        super().closeEvent(event)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
def main():
    set_high_priority()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Orbit Spotlight")

    # Ícone de lupa (desenhado em alta resolução para ficar nítido)
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#4a9eff"))
    pen.setWidth(7)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    # Anel da lupa
    painter.drawEllipse(10, 10, 30, 30)
    # Cabo da lupa
    painter.drawLine(37, 37, 54, 54)
    painter.end()

    tray = QSystemTrayIcon(QIcon(px), app)
    tray.setToolTip("Orbit Spotlight  —  Ctrl+' para abrir")

    tray_menu = QMenu()
    act_show = QAction("Abrir Orbit Spotlight  (Ctrl+')", tray_menu)
    act_quit = QAction("Fechar", tray_menu)
    tray_menu.addAction(act_show)
    tray_menu.addSeparator()
    tray_menu.addAction(act_quit)
    tray.setContextMenu(tray_menu)
    tray.show()

    launcher = Launcher()

    # Hotkey global Ctrl+' para ABNT2
    # Anti-double-toggle: quando ambos os hooks (Win32 + keyboard) estão ativos,
    # Ctrl+' pode disparar toggle_launcher 2x. Debounce de 300ms impede isso.
    _last_toggle = [0.0]

    def toggle_launcher():
        now = time.monotonic()
        if now - _last_toggle[0] < 0.3:
            return  # ignora disparo duplicado
        _last_toggle[0] = now

        launcher._toggle_signal.emit()

    # ── Estratégia dupla para o atalho global ──────────────────────────
    # 1. Win32 RegisterHotKey (primário) — robusto, sobrevive a sleep/UAC.
    # 2. keyboard library (fallback)     — WH_KEYBOARD_LL hook, pode morrer.
    # 3. Watchdog periódico              — re-registra se o hook morrer.

    HOTKEY_ID    = 0x0001
    MOD_CONTROL  = 0x0002
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY    = 0x0312

    # Detecta o VK do apóstrofo dinamicamente via VkKeyScanW.
    # Isso funciona em qualquer layout (ABNT2, US-Intl, etc.).
    _vk_scan = ctypes.windll.user32.VkKeyScanW(ord("'"))
    if _vk_scan == -1:
        # Fallback: VK_OEM_7 é o padrão em US layout
        VK_APOSTROPHE = 0xDE
        log.warning("hotkey: VkKeyScanW(') retornou -1, usando fallback 0xDE")
    else:
        VK_APOSTROPHE = _vk_scan & 0xFF
        log.info("hotkey: VkKeyScanW(') = 0x%02X (VK=0x%02X)", _vk_scan, VK_APOSTROPHE)

    _hotkey_state = {
        "win32_ok": False,       # RegisterHotKey ativo
        "keyboard_ok": False,    # keyboard lib ativo
        "keyboard_hook_id": None,
        "tries": 0,
    }

    # ── Método 1: Win32 RegisterHotKey (mais confiável) ──────
    class HotkeyFilter(QAbstractNativeEventFilter):
        """Intercepta WM_HOTKEY no event loop do Qt."""
        def nativeEventFilter(self, eventType, message):
            if eventType == b"windows_generic_MSG":
                try:
                    msg = ctypes.wintypes.MSG.from_address(int(message))
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        toggle_launcher()
                        return True, 0
                except Exception:
                    pass
            return False, 0

    _hotkey_filter = HotkeyFilter()

    def _register_win32_hotkey():
        """Tenta registrar via RegisterHotKey do Windows."""
        if _hotkey_state["win32_ok"]:
            return True
        try:
            # Tenta desregistrar primeiro (caso tenha sobrado de instância anterior)
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        ok = ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_CONTROL | MOD_NOREPEAT, VK_APOSTROPHE
        )
        if ok:
            _hotkey_state["win32_ok"] = True
            app.installNativeEventFilter(_hotkey_filter)
            log.info("hotkey: RegisterHotKey(Ctrl+VK=0x%02X) OK", VK_APOSTROPHE)
        else:
            err = ctypes.GetLastError()
            log.warning("hotkey: RegisterHotKey falhou (err=%d)", err)
        return bool(ok)

    # ── Método 2: keyboard library (fallback) ──────
    def _register_keyboard_hotkey():
        """Registra via biblioteca keyboard (WH_KEYBOARD_LL hook)."""
        if _hotkey_state["keyboard_ok"]:
            return True
        try:
            # Remove hooks antigos antes de re-registrar
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
            hook = keyboard.add_hotkey("ctrl+'", toggle_launcher)
            _hotkey_state["keyboard_ok"] = True
            _hotkey_state["keyboard_hook_id"] = hook
            log.info("hotkey: keyboard.add_hotkey(ctrl+') OK")
            return True
        except Exception as e:
            log.warning("hotkey: keyboard.add_hotkey falhou: %s", e)
            _hotkey_state["keyboard_ok"] = False
            return False

    # ── Verificação de saúde do hook ──────
    def _test_keyboard_hook_alive() -> bool:
        """Verifica se o hook WH_KEYBOARD_LL do keyboard ainda está ativo.
        
        Checa se a thread do listener do keyboard ainda está rodando.
        Se o Windows matou o hook, a thread morre ou os hooks internos ficam vazios.
        """
        try:
            listener = keyboard._listener
            if listener is None:
                return False
            # Verifica se a thread de listening ainda está viva
            if hasattr(listener, 'listening') and not listener.listening:
                return False
            # Verifica se ainda tem hooks registrados
            if hasattr(keyboard, '_hotkeys') and not keyboard._hotkeys:
                return False
            return True
        except Exception:
            return False

    # ── Registro inicial + watchdog ──────
    def register_all():
        """Tenta ambos os métodos de registro."""
        _hotkey_state["tries"] += 1
        attempt = _hotkey_state["tries"]

        win32_ok = _register_win32_hotkey()
        kb_ok = _register_keyboard_hotkey()

        if win32_ok or kb_ok:
            log.info("hotkey: registro OK (tentativa %d, win32=%s, keyboard=%s)",
                     attempt, win32_ok, kb_ok)
        else:
            log.error("hotkey: AMBOS falharam (tentativa %d)", attempt)
            if attempt < 15:
                QTimer.singleShot(3000, register_all)

    def watchdog_check():
        """Verificação periódica — re-registra se ambos os hooks morreram."""
        win32_alive = _hotkey_state["win32_ok"]
        kb_alive = _hotkey_state["keyboard_ok"] and _test_keyboard_hook_alive()

        if not kb_alive and _hotkey_state["keyboard_ok"]:
            log.warning("watchdog: hook keyboard morreu — re-registrando")
            _hotkey_state["keyboard_ok"] = False
            _register_keyboard_hotkey()

        if not win32_alive and not kb_alive:
            log.warning("watchdog: AMBOS os hooks mortos — re-registrando tudo")
            _hotkey_state["win32_ok"] = False
            register_all()

    # 1a tentativa após 1.5s (dá tempo do shell carregar no boot)
    QTimer.singleShot(1500, register_all)
    # Reforço extra no boot
    QTimer.singleShot(5000, register_all)

    # Watchdog a cada 30s para detectar hooks mortos e re-registrar
    _watchdog = QTimer()
    _watchdog.setInterval(30_000)
    _watchdog.timeout.connect(watchdog_check)
    QTimer.singleShot(10_000, _watchdog.start)


    act_show.triggered.connect(launcher._do_show)
    act_quit.triggered.connect(app.quit)
    tray.activated.connect(
        lambda reason: launcher._do_show() if reason == QSystemTrayIcon.DoubleClick else None
    )

    # Por padrao inicia minimizado na bandeja (usado ao iniciar com o Windows).
    # Use --show / --window para abrir a janela direto (execucao manual de teste).
    show_window = "--show" in sys.argv or "--window" in sys.argv
    if show_window:
        launcher._do_show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()