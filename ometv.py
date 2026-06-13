# OmeTV Clean Browser v3.0
# Download, setup and run - all in one file.

import os, sys, shutil, socket, subprocess, tarfile, tempfile
import threading, time, uuid, random, urllib.request, json
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
OME_URL = "https://ome.tv"
TOR_BV = "15.0.15"
TOR_TGZ = f"tor-expert-bundle-windows-x86_64-{TOR_BV}.tar.gz"
TOR_URL = f"https://dist.torproject.org/torbrowser/{TOR_BV}/{TOR_TGZ}"
BASE    = Path(__file__).parent.resolve()
TOR_DIR = BASE / "tor"
TOR_EXE = TOR_DIR / "tor.exe"
TOR_LOG = TOR_DIR / "tor.log"

DEPS = ["PyQt6", "PyQt6-WebEngine", "stem"]

# ── Setup UI (tkinter - no external deps) ────────────────────────────

class SetupUI:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.root = tk.Tk()
        self.root.title("OmeTV Clean Browser - Setup")
        self.root.geometry("520x300")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        try: self.root.iconbitmap(default="")
        except: pass

        cx = self.root.winfo_screenwidth()
        cy = self.root.winfo_screenheight()
        self.root.geometry(f"+{cx//2-260}+{cy//2-150}")

        container = tk.Frame(self.root, bg="#1a1a2e")
        container.pack(expand=True, fill="both", padx=30, pady=25)

        tk.Label(container, text="OmeTV Clean Browser",
                 font=("Segoe UI", 20, "bold"),
                 fg="#e94560", bg="#1a1a2e").pack(anchor="w")

        tk.Label(container, text="Installing dependencies...\nThis may take a few minutes.",
                 font=("Segoe UI", 10),
                 fg="#94a3b8", bg="#1a1a2e", justify="left").pack(anchor="w", pady=(6, 16))

        self.status = tk.Label(container, text="Preparing...",
                               font=("Segoe UI", 9),
                               fg="#c0c0d0", bg="#1a1a2e", anchor="w")
        self.status.pack(fill="x")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("green.Horizontal.TProgressbar",
                        troughcolor="#0f3460", background="#4ade80",
                        bordercolor="#0f3460", lightcolor="#4ade80",
                        darkcolor="#4ade80")

        self.bar = ttk.Progressbar(container, mode="indeterminate",
                                   style="green.Horizontal.TProgressbar")
        self.bar.pack(fill="x", pady=(10, 0))

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.update()

    def update(self, text):
        self.status.config(text=text)
        self.root.update()

    def done(self, success=True):
        self.bar.stop()
        if success:
            self.status.config(text="Setup complete! Starting browser...", fg="#4ade80")
            self.root.update()
            time.sleep(1)
        self.root.destroy()


def run_setup():
    ui = SetupUI()
    ui.root.after(100, lambda: _do_setup(ui))
    ui.root.mainloop()


def _do_setup(ui):
    try:
        _install_python_deps(ui)
        _download_tor(ui)
        ui.done(True)
    except Exception as e:
        ui.status.config(text=f"Error: {e}", fg="#e94560")
        ui.root.update()
        time.sleep(3)
        ui.done(False)
        sys.exit(1)


def _install_python_deps(ui):
    ui.update("Checking Python dependencies...")
    missing = []
    try: import PyQt6
    except: missing.append("PyQt6")
    try: from PyQt6 import QtWebEngineWidgets
    except: missing.append("PyQt6-WebEngine") if "PyQt6-WebEngine" not in missing else None
    try: import stem
    except: missing.append("stem")

    if not missing:
        ui.update("All dependencies already installed.")
        return

    ui.update(f"Downloading: {', '.join(missing)}...")

    cmd = [sys.executable, "-m", "pip", "install", "--user", "--quiet"]
    if sys.executable.endswith("_py.exe"):
        cmd = ["py", "-3", "-m", "pip", "install", "--user", "--quiet"]

    total = len(missing)
    for i, pkg in enumerate(missing):
        ui.update(f"Installing {pkg} ({i+1}/{total})...")
        r = subprocess.run(cmd + [pkg], capture_output=True, timeout=180)
        if r.returncode != 0:
            # Try without --user
            r2 = subprocess.run(cmd[:-1] + [pkg], capture_output=True, timeout=180)
            if r2.returncode != 0:
                err = (r.stderr + r2.stderr).decode("utf-8", errors="ignore")[:200]
                raise Exception(f"Failed to install {pkg}: {err}")

    ui.update("Dependencies installed. Verifying...")


def _download_tor(ui):
    if TOR_EXE.exists():
        ui.update("Tor already downloaded.")
        return

    os.makedirs(TOR_DIR, exist_ok=True)
    tgz = TOR_DIR / TOR_TGZ

    ui.update(f"Downloading Tor... (21 MB)")

    def hook(b, bs, ts):
        if ts > 0:
            pct = int(b * bs * 100 / ts)
            ui.update(f"Downloading Tor... {pct}%")

    try:
        urllib.request.urlretrieve(TOR_URL, tgz, hook)
    except Exception as e:
        raise Exception(f"Tor download failed: {e}")

    ui.update("Extracting Tor...")
    try:
        with tarfile.open(tgz) as tf:
            tf.extractall(TOR_DIR, filter="data")
        os.remove(tgz)
        found = list(TOR_DIR.rglob("tor.exe"))
        if found:
            shutil.copy2(found[0], TOR_EXE)
            for dll in found[0].parent.glob("*.dll"):
                shutil.copy2(dll, TOR_DIR / dll.name)
        for item in list(TOR_DIR.iterdir()):
            if item.is_dir() and item.name.startswith("tor-"):
                shutil.rmtree(item, ignore_errors=True)
    except Exception as e:
        raise Exception(f"Tor extraction failed: {e}")

    if not TOR_EXE.exists():
        raise Exception("tor.exe not found after extraction")

    ui.update("Tor ready.")


# ── Tor Manager ─────────────────────────────────────────────────────

def start_tor():
    os.makedirs(TOR_DIR / "data", exist_ok=True)
    torrc = TOR_DIR / "torrc"
    torrc.write_text(
        f"SOCKSPort 127.0.0.1:9050\n"
        f"ControlPort 127.0.0.1:9051\n"
        f"DataDirectory {(TOR_DIR / 'data').as_posix()}\n"
        f"CircuitBuildTimeout 30\n"
        f"MaxCircuitDirtiness 600\n"
        f"Log notice file {TOR_LOG.as_posix()}\n"
        f"AvoidDiskWrites 1\n"
    )

    proc = subprocess.Popen(
        [str(TOR_EXE), "-f", str(torrc)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    for i in range(60):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", 9050))
            s.close()
            return proc
        except:
            time.sleep(1)
    return proc


# ── Browser (PyQt6) ──────────────────────────────────────────────────

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--proxy-server=socks5://127.0.0.1:9050 "
    "--proxy-bypass-list=*.facebook.com;*.fbcdn.net;*.google.com;*.googleapis.com;*.gstatic.com;*.googleusercontent.com "
    "--disable-blink-features=AutomationControlled "
    "--disable-webrtc-hw-encoding "
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp "
    "--webrtc-ip-handling-policy=disable_non_proxied_udp "
    "--disable-sync --disable-background-networking "
    "--disable-component-update --no-first-run"
)

from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QMessageBox, QFrame, QMenuBar, QMenu
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings


class LoginPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.popups = []

    def createWindow(self, wtype):
        types = (QWebEnginePage.WebWindowType.WebBrowserTab,
                 QWebEnginePage.WebWindowType.WebBrowserBackgroundTab,
                 QWebEnginePage.WebWindowType.WebDialog)
        if wtype in types:
            pw = QWebEngineView()
            pw.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            pw.setPage(LoginPage(self.profile(), pw))
            pw.setMinimumSize(700, 500)
            pw.resize(800, 600)
            if self.parent() and self.parent().window():
                c = self.parent().window().frameGeometry().center()
                pw.move(c.x() - 400, c.y() - 300)
            pw.show()
            self.popups.append(pw)
            pw.destroyed.connect(lambda w=pw: self.popups.remove(w) if w in self.popups else None)
            return pw.page()
        return super().createWindow(wtype)


class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tor_proc = None
        self.temp_dir = None
        self.sid = uuid.uuid4().hex[:12]
        self._uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        ]
        self.ua = random.choice(self._uas)
        self.lang = random.choice([
            "en-US,en;q=0.9", "pt-BR,pt;q=0.9,en;q=0.8",
            "es-ES,es;q=0.9,en;q=0.8",
        ])
        self._ui()
        self._profile()
        self._load()

    def _ui(self):
        self.setWindowTitle("OmeTV Clean Browser")
        self.resize(1280, 720)
        self.setMinimumSize(800, 550)

        c = QWidget(); self.setCentralWidget(c)
        l = QVBoxLayout(c); l.setContentsMargins(0,0,0,0); l.setSpacing(0)

        bar = QFrame(); bar.setObjectName("bar"); bar.setFixedHeight(44)
        hl = QHBoxLayout(bar); hl.setContentsMargins(8,4,8,4)
        logo = QLabel("OmeTV Clean"); logo.setObjectName("logo"); hl.addWidget(logo)
        self.st = QLabel("Starting Tor..."); self.st.setObjectName("st")
        hl.addWidget(self.st); hl.addStretch()
        self.lb = QLabel(f"SID: {self.sid[:8]}"); self.lb.setObjectName("sid")
        hl.addWidget(self.lb); hl.addSpacing(6)

        for t, cb in [("New IP", self._newid), ("Reload", lambda: self.bw.reload()), ("New Session", self._reset)]:
            b = QPushButton(t); b.setObjectName("btnr" if t=="New Session" else "btn")
            b.clicked.connect(cb); hl.addWidget(b)

        l.addWidget(bar)
        self.bw = QWebEngineView(); l.addWidget(self.bw)

        m = self.menuBar(); sm = m.addMenu("Session")
        for t,cb in [("New IP (Tor)", self._newid), ("New Session", self._reset)]:
            a=QAction(t,self); a.triggered.connect(cb); sm.addAction(a)
        sm.addSeparator(); a=QAction("Exit",self); a.triggered.connect(self.close); sm.addAction(a)
        h=m.addMenu("Help")
        a=QAction("About",self); a.triggered.connect(lambda:
            QMessageBox.about(self,"OmeTV Clean Browser",
                "OmeTV Clean Browser v3.0\n\nChromium + Tor embutido.\nAuto-reset a cada sessao.\nLogin OAuth liberado.")); h.addAction(a)

        sb=QStatusBar(); sb.setObjectName("sb"); self.setStatusBar(sb)
        sb.showMessage(f"Session: {self.sid}",0)

    def _profile(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"ometv_{self.sid}_"))
        self.prof = QWebEngineProfile(f"ometv_{self.sid}", self.bw)
        self.prof.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self.prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.prof.setHttpCacheMaximumSize(50*1024*1024)
        sp = str(self.temp_dir / "storage"); os.makedirs(sp, exist_ok=True)
        self.prof.setPersistentStoragePath(sp)

        s = self.prof.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self.bw.setPage(LoginPage(self.prof, self.bw))

    def _load(self):
        self.bw.load(QUrl(OME_URL))

    def _newid(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5); s.connect(("127.0.0.1",9051))
                s.sendall(b"AUTHENTICATE\r\n"); s.recv(1024)
                s.sendall(b"SIGNAL NEWNYM\r\n")
        except: pass

    def _reset(self):
        r = QMessageBox.question(self,"New Session",
            "Reset everything and start fresh?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes: return
        self._newid(); od = self.temp_dir
        self.sid = uuid.uuid4().hex[:12]; self.ua = random.choice(self._uas)
        self.lb.setText(f"SID: {self.sid[:8]}")
        self.bw.setPage(None); self.prof.deleteLater()
        self._profile(); self._load()
        if od and od.exists():
            threading.Thread(target=lambda: shutil.rmtree(od, ignore_errors=True), daemon=True).start()

    def closeEvent(self, ev):
        if self.temp_dir and self.temp_dir.exists():
            try: shutil.rmtree(self.temp_dir, ignore_errors=True)
            except: pass
        ev.accept()


# ── Main ─────────────────────────────────────────────────────────────

def cleanup_system():
    print("[*] Cleaning system...")
    try: subprocess.run(["ipconfig","/flushdns"],capture_output=True,check=True)
    except: pass
    try: subprocess.run(["netsh","int","ip","reset"],capture_output=True)
    except: pass
    try: subprocess.run(["netsh","winsock","reset"],capture_output=True)
    except: pass
    print("  + System cleaned")


def main():
    print("="*50)
    print("  OmeTV Clean Browser v3.0")
    print("="*50)

    need_setup = False
    try: import PyQt6
    except: need_setup = True
    try: from PyQt6 import QtWebEngineWidgets
    except: need_setup = True
    try: import stem
    except: need_setup = True
    if not TOR_EXE.exists(): need_setup = True

    if need_setup:
        print("[*] First run detected. Opening setup wizard...")
        run_setup()
        import importlib
        importlib.invalidate_caches()

    cleanup_system()

    if not TOR_EXE.exists():
        print("[ERROR] Tor not found. Run again to download.")
        input("Press Enter..."); return

    tor_proc = start_tor()
    print("  + Tor connected")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow{background:#1a1a2e}
        #bar{background:#16213e;border-bottom:1px solid #0f3460}
        #logo{color:#e94560;font-size:15px;font-weight:bold;padding:0 6px}
        #st{color:#4ade80;font-size:12px}
        #sid{color:#64748b;font-size:11px}
        QPushButton#btn{background:#0f3460;color:#e0e0e0;border:none;padding:5px 12px;border-radius:3px;font-size:11px}
        QPushButton#btn:hover{background:#1a4a8a}
        QPushButton#btnr{background:#e94560;color:#fff;border:none;padding:5px 12px;border-radius:3px;font-size:11px;font-weight:bold}
        QPushButton#btnr:hover{background:#c73650}
        #sb{background:#16213e;color:#94a3b8;border-top:1px solid #0f3460;font-size:11px}
        QMenuBar{background:#0f0f23;color:#c0c0d0;border-bottom:1px solid #0f3460}
        QMenuBar::item:selected{background:#0f3460}
        QMenu{background:#16213e;color:#c0c0d0;border:1px solid #0f3460}
        QMenu::item:selected{background:#0f3460}
    """)

    w = BrowserWindow(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
