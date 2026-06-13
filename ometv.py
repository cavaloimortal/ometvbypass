# OmeTV Clean Browser v3.2
# Download, setup and run - all in one file.

import os, sys, shutil, socket, subprocess, tarfile, tempfile
import threading, time, uuid, random, urllib.request, json
import struct, select
from pathlib import Path
from urllib.parse import urlparse

# ── Config ──────────────────────────────────────────────────────────
OME_URL = "https://ome.tv"
TOR_BV = "15.0.15"
TOR_TGZ = f"tor-expert-bundle-windows-x86_64-{TOR_BV}.tar.gz"
TOR_URL = f"https://dist.torproject.org/torbrowser/{TOR_BV}/{TOR_TGZ}"

BASE = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OmeTVCleanBrowser"
TOR_DIR = BASE / "tor"
TOR_EXE = TOR_DIR / "tor.exe"
TOR_LOG = TOR_DIR / "tor.log"
PROXY_PORT = 8080

DEPS = ["PyQt6", "PyQt6-WebEngine", "stem"]

# ── Local proxy: only .ome.tv through Tor ────────────────────────────

def socks5_connect(host, port, proxy_host="127.0.0.1", proxy_port=9050):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    try:
        s.connect((proxy_host, proxy_port))
        s.sendall(bytes([5, 1, 0]))
        data = s.recv(2)
        if data != bytes([5, 0]):
            raise ConnectionError("SOCKS5 auth failed")
        host_bytes = host.encode("idna")
        req = bytes([5, 1, 0, 3, len(host_bytes)]) + host_bytes + struct.pack(">H", port)
        s.sendall(req)
        resp = s.recv(4)
        if resp[1] != 0:
            s.close()
            raise ConnectionError(f"SOCKS5 connect error {resp[1]}")
        if resp[3] == 1:
            s.recv(6)
        elif resp[3] == 3:
            alen = s.recv(1)[0]
            s.recv(alen + 2)
        elif resp[3] == 4:
            s.recv(18)
        s.settimeout(None)
        return s
    except:
        s.close()
        raise


def start_local_proxy(tor_host="127.0.0.1", tor_port=9050, listen_port=PROXY_PORT):
    import socketserver

    def use_tor(host):
        h = host.lower().strip(".")
        return h == "ome.tv" or h.endswith(".ome.tv")

    class ProxyHandler(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                first = self.rfile.readline()
                if not first:
                    return
                if first.startswith(b"CONNECT "):
                    parts = first.split()
                    hp = parts[1].decode()
                    h, _, p = hp.partition(":")
                    p = int(p) if p else 443
                    while self.rfile.readline() != b"\r\n":
                        pass
                    self._tunnel(h, p)
                else:
                    self._http(first)
            except:
                pass

        def _tunnel(self, host, port):
            try:
                if use_tor(host):
                    remote = socks5_connect(host, port, tor_host, tor_port)
                else:
                    remote = socket.create_connection((host, port), timeout=15)
                self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                _relay(self.request, remote)
            except:
                try: self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                except: pass

        def _http(self, first):
            try:
                parts = first.split()
                if len(parts) < 2:
                    return
                url = parts[1].decode()
                parsed = urlparse(url)
                host, port = parsed.hostname, parsed.port or 80
                if not host:
                    return
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                new_first = f"{parts[0].decode()} {path} HTTP/1.1\r\n".encode()
                rest = b""
                while True:
                    line = self.rfile.readline()
                    rest += line
                    if line == b"\r\n" or not line:
                        break
                if use_tor(host):
                    remote = socks5_connect(host, port, tor_host, tor_port)
                else:
                    remote = socket.create_connection((host, port), timeout=15)
                remote.sendall(new_first + rest)
                _relay(self.request, remote)
            except:
                pass

    def _relay(s1, s2):
        s1.settimeout(None); s2.settimeout(None)
        socks = [s1, s2]
        try:
            while True:
                r, _, _ = select.select(socks, [], [], 30)
                if not r:
                    break
                for s in r:
                    d = s.recv(65536)
                    if not d:
                        return
                    (s2 if s is s1 else s1).sendall(d)
        except:
            pass
        finally:
            try: s1.close()
            except: pass
            try: s2.close()
            except: pass

    sv = socketserver.ThreadingTCPServer(("127.0.0.1", listen_port), ProxyHandler)
    sv.daemon_threads = True
    sv.allow_reuse_address = True
    t = threading.Thread(target=sv.serve_forever, daemon=True)
    t.start()
    return sv


# ── Setup UI (tkinter - no external deps) ────────────────────────────

class SetupUI:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.root = tk.Tk()
        self.root.title("OmeTV Clean Browser - Setup")
        self.root.geometry("480x260")
        self.root.resizable(False, False)
        self.root.configure(bg="#0a0a1a")

        try: self.root.iconbitmap(default="")
        except: pass

        cx = self.root.winfo_screenwidth()
        cy = self.root.winfo_screenheight()
        self.root.geometry(f"+{cx//2-240}+{cy//2-130}")

        container = tk.Frame(self.root, bg="#0a0a1a")
        container.pack(expand=True, fill="both", padx=28, pady=22)

        tk.Label(container, text="OmeTV Clean Browser",
                 font=("Segoe UI", 18, "bold"),
                 fg="#a78bfa", bg="#0a0a1a").pack(anchor="w")

        tk.Label(container, text="Installing dependencies...\nThis may take a few minutes.",
                 font=("Segoe UI", 10),
                 fg="#7a7a9a", bg="#0a0a1a", justify="left").pack(anchor="w", pady=(6, 14))

        self.status = tk.Label(container, text="Preparing...",
                               font=("Segoe UI", 9),
                               fg="#a0a0c0", bg="#0a0a1a", anchor="w")
        self.status.pack(fill="x")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("green.Horizontal.TProgressbar",
                        troughcolor="#1a1a3a", background="#a78bfa",
                        bordercolor="#1a1a3a", lightcolor="#a78bfa",
                        darkcolor="#7c5cbf")

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
    f"--proxy-server=http://127.0.0.1:{PROXY_PORT} "
    "--proxy-bypass-list=127.0.0.1;localhost "
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


class MainPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._popups = []
        try:
            self.permissionRequested.connect(self._grant_perm)
        except AttributeError:
            pass

    def _grant_perm(self, *args):
        try:
            if len(args) == 2:
                self.setFeaturePermission(args[0], args[1],
                    QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
            elif len(args) == 1:
                args[0].grant()
        except:
            pass

    def createWindow(self, wtype):
        if wtype in (
            QWebEnginePage.WebWindowType.WebBrowserTab,
            QWebEnginePage.WebWindowType.WebBrowserBackgroundTab,
            QWebEnginePage.WebWindowType.WebDialog,
        ):
            pw = QWebEngineView()
            pw.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            popup_page = QWebEnginePage(self.profile(), pw)
            popup_page.windowCloseRequested.connect(pw.close)
            pw.setPage(popup_page)
            pw.setMinimumSize(700, 500)
            pw.resize(800, 600)
            if self.parent() and self.parent().window():
                c = self.parent().window().frameGeometry().center()
                pw.move(c.x() - 400, c.y() - 300)
            pw.show()
            self._popups.append(pw)
            pw.destroyed.connect(lambda w=pw: self._popups.remove(w) if w in self._popups else None)
            return popup_page
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
        self.setMinimumSize(900, 580)

        c = QWidget(); self.setCentralWidget(c)
        l = QVBoxLayout(c); l.setContentsMargins(0,0,0,0); l.setSpacing(0)

        # ── Top bar ──
        bar = QFrame(); bar.setObjectName("bar"); bar.setFixedHeight(48)
        hl = QHBoxLayout(bar); hl.setContentsMargins(14,0,10,0); hl.setSpacing(0)

        logo = QLabel("OmeTV Clean"); logo.setObjectName("logo")
        hl.addWidget(logo); hl.addSpacing(10)

        self.indicator = QLabel(); self.indicator.setObjectName("indicator")
        self.indicator.setFixedSize(8, 8); hl.addWidget(self.indicator); hl.addSpacing(6)

        self.st = QLabel("Starting Tor..."); self.st.setObjectName("st")
        hl.addWidget(self.st); hl.addStretch()

        sid_label = QLabel(f"SID {self.sid[:8]}"); sid_label.setObjectName("sid")
        hl.addWidget(sid_label); hl.addSpacing(8)

        for t, cb, kind in [
            ("New IP", self._newid, ""),
            ("Reload", lambda: self.bw.reload(), ""),
            ("New Session", self._reset, "danger"),
        ]:
            b = QPushButton(t); b.setObjectName(f"btn_{kind}" if kind else "btn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cb); hl.addWidget(b)

        l.addWidget(bar)
        self.bw = QWebEngineView(); l.addWidget(self.bw)

        # ── Menu ──
        m = self.menuBar(); m.setObjectName("mb")
        sm = m.addMenu("Session")
        for t,cb in [("New IP (Tor)", self._newid), ("New Session", self._reset)]:
            a=QAction(t,self); a.triggered.connect(cb); sm.addAction(a)
        sm.addSeparator(); a=QAction("Exit",self); a.triggered.connect(self.close); sm.addAction(a)
        h=m.addMenu("Help")
        a=QAction("About",self); a.triggered.connect(self._about); h.addAction(a)

        # ── Status bar ──
        sb=QStatusBar(); sb.setObjectName("sb"); self.setStatusBar(sb)
        self.sb_label = QLabel(f"Session {self.sid}")
        self.sb_label.setObjectName("sbl")
        sb.addPermanentWidget(self.sb_label)

        self._update_indicator("yellow")

    def _update_indicator(self, color):
        colors = {"green": "#4ade80", "yellow": "#eab308", "red": "#e94560"}
        c = colors.get(color, "#eab308")
        self.indicator.setStyleSheet(f"background:{c};border-radius:4px;")
        self.indicator.setToolTip({"green":"Connected","yellow":"Starting...","red":"Error"}.get(color, ""))

    def _about(self):
        QMessageBox.about(self, "OmeTV Clean Browser",
            "OmeTV Clean Browser v3.2\n\n"
            "Chromium engine + embedded Tor.\n"
            "Auto-reset session on every run.\n"
            "OAuth login with local proxy.")

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

        self._page = MainPage(self.prof, self.bw)
        self.bw.setPage(self._page)

    def _load(self):
        self.st.setText("Connected")
        self._update_indicator("green")
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
    print("  OmeTV Clean Browser v3.2")
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

    proxy = start_local_proxy()
    print(f"  + Local proxy on 127.0.0.1:{PROXY_PORT}")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow{background:#0a0a1a}
        QWidget{color:#e0e0f0;font-family:Segoe UI,sans-serif;font-size:12px}

        #bar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #12122a,stop:1 #1a1a3a);border-bottom:1px solid #2a2a4a}
        #logo{color:#a78bfa;font-size:14px;font-weight:700;letter-spacing:.5px}
        #st{color:#94a3b8;font-size:11px}
        #sid{background:#1e1e3a;color:#7c7caa;border-radius:8px;padding:3px 10px;font-size:10px;font-weight:600;font-family:Consolas,monospace}

        QPushButton#btn{background:#1e1e3e;color:#c0c0e0;border:1px solid #2e2e5e;padding:6px 14px;border-radius:6px;font-size:11px;font-weight:500}
        QPushButton#btn:hover{background:#2a2a5a;border-color:#4a4a8a;color:#fff}
        QPushButton#btn:pressed{background:#3a3a6a}
        QPushButton#btn_danger{background:#8b1a3a;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-size:11px;font-weight:600}
        QPushButton#btn_danger:hover{background:#b02050}
        QPushButton#btn_danger:pressed{background:#6e142e}

        #sb{background:#0d0d20;color:#6a6a8a;border-top:1px solid #1a1a3a;font-size:11px;padding:2px 10px}
        #sbl{color:#5a5a7a;font-family:Consolas,monospace;font-size:10px}

        QMenuBar{background:#0a0a1a;color:#8888b0;border-bottom:1px solid #1a1a3a;padding:2px}
        QMenuBar::item{padding:4px 14px;border-radius:4px}
        QMenuBar::item:selected{background:#1e1e3e;color:#fff}
        QMenu{background:#12122a;color:#c0c0e0;border:1px solid #2a2a4a;border-radius:6px;padding:4px}
        QMenu::item{padding:6px 24px;border-radius:4px}
        QMenu::item:selected{background:#2a2a5a;color:#fff}
        QMenu::separator{background:#2a2a4a;height:1px;margin:4px 12px}

        QToolTip{background:#1e1e3e;color:#e0e0f0;border:1px solid #3a3a6a;border-radius:4px;padding:4px 8px;font-size:11px}
    """)

    w = BrowserWindow(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
