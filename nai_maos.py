"""
NAI · Mundo SENAI — reconhecimento de mãos (roda junto com a página da NAI)

O que faz:
  • lê a webcam da frente da TV;
  • conta quantos dedos a pessoa mostra (1 a 5) e acompanha a ponta do indicador (toque no ar);
  • manda essas informações em tempo real para a página da NAI (WebSocket ws://127.0.0.1:8787);
  • abre a página no Microsoft Edge em tela cheia (modo quiosque).

Uso:  python nai_maos.py              (normal)
      python nai_maos.py --janela     (abre também uma janela de teste com a câmera e os pontos da mão)
      python nai_maos.py --camera 1   (usa outra câmera)
      python nai_maos.py --monitor 2  (abre a NAI na tela/monitor 2)
      python nai_maos.py --sem-navegador
Para sair: aperte F nesta janela (fecha a tela da NAI e o programa) — ou feche esta janela.
"""
import argparse
import asyncio
import base64
import collections
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

try:
    import cv2
    import mediapipe as mp
    import websockets
except ImportError as e:
    print("\n[ERRO] Falta instalar as bibliotecas. Rode primeiro o arquivo  instalar.bat\n", e)
    input("Aperte Enter para sair...")
    sys.exit(1)

PORTA = 8787
ROSTO_MIN = 0.06          # tamanho mínimo do rosto na imagem (fração da largura) para contar como "parou na frente"
PASTA = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(PASTA, "nai_config.json")
TITULO = "NAI – Mundo SENAI"            # título da página (usado para achar a janela)


def ler_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_config():
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except Exception:
        pass


config = ler_config()


# ----------------------------------------------------------------------------- telas (monitores) — Windows
if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MONITORENUMPROC, wintypes.LPARAM]
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFOEXW)]
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]

    # coordenadas em pixels reais (sem isso, telas com zoom de 125%/150% dão posições erradas)
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass


def listar_monitores():
    """Telas ligadas ao computador. A tela 1 é sempre a principal; as outras seguem da esquerda para a direita."""
    if os.name != "nt":
        return []
    mons = []

    def cb(h, hdc, r, lp):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(h, ctypes.byref(mi)):
            rc = mi.rcMonitor
            mons.append({"x": rc.left, "y": rc.top, "w": rc.right - rc.left, "h": rc.bottom - rc.top,
                         "principal": bool(mi.dwFlags & 1), "dev": mi.szDevice.replace("\\\\.\\", "")})
        return True
    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    mons.sort(key=lambda m: (not m["principal"], m["x"], m["y"]))
    for i, m in enumerate(mons, 1):
        m["n"] = i
        m["desc"] = (f'Tela {i}: {m["w"]}x{m["h"]}' + (" · vertical" if m["h"] > m["w"] else "")
                     + (" · principal" if m["principal"] else ""))
    return mons


def monitor_escolhido():
    mons = listar_monitores()
    n = config.get("monitor") or 1
    return next((m for m in mons if m["n"] == n), mons[0] if mons else None)


def achar_janela_nai():
    if os.name != "nt":
        return None
    pid_nav = navegador["proc"].pid if navegador.get("proc") else -1
    por_pid, por_titulo = [], []

    def cb(hwnd, lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if not (cls.value.startswith("Chrome_WidgetWin") or cls.value == "MozillaWindowClass"):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if not buf.value:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == pid_nav:
            por_pid.append(hwnd)
        elif TITULO in buf.value:
            por_titulo.append(hwnd)
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    lista = por_pid or por_titulo
    return lista[0] if lista else None


def janela_esta_na_tela(hwnd, m):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    return m["x"] <= cx < m["x"] + m["w"] and m["y"] <= cy < m["y"] + m["h"]


def encaixar_janela(m, espera=0.0):
    """Coloca a janela da NAI ocupando a tela m. Devolve True se deu certo."""
    fim = time.time() + espera
    h = achar_janela_nai()
    while not h and time.time() < fim:
        time.sleep(0.5)
        h = achar_janela_nai()
    if not h:
        return False
    if janela_esta_na_tela(h, m):
        return True
    user32.SetWindowPos(h, None, m["x"], m["y"], m["w"], m["h"], 0x0004 | 0x0040)   # SWP_NOZORDER | SWP_SHOWWINDOW
    time.sleep(1.0)
    user32.SetForegroundWindow(h)
    return janela_esta_na_tela(h, m)


def mudar_tela(n):
    mons = listar_monitores()
    m = next((x for x in mons if x["n"] == n), None)
    if not m:
        print(f"[tela] não existe a tela {n}.")
        return
    config["monitor"] = n
    salvar_config()
    print(f"[tela] levando a NAI para a {m['desc']}...")
    if encaixar_janela(m):
        print("[tela] pronto.")
        return
    if navegador.get("html"):                          # não deu para mover: reabre direto na tela escolhida
        print("[tela] reabrindo a NAI na tela escolhida...")
        fechar_navegador()
        time.sleep(1)
        abrir_navegador(navegador["html"])


IDENTIFICAR = r"""
import sys, json, ctypes, tkinter as tk
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass
mons = json.loads(sys.argv[1]); root = tk.Tk(); root.withdraw()
for m in mons:
    w = tk.Toplevel(root); w.overrideredirect(True); w.attributes('-topmost', True); w.configure(bg='#e6007e')
    W, H = 420, 340
    w.geometry(f"{W}x{H}+{m['x'] + (m['w'] - W) // 2}+{m['y'] + (m['h'] - H) // 2}")
    tk.Label(w, text=str(m['n']), font=('Segoe UI', 160, 'bold'), fg='white', bg='#e6007e').pack(expand=True)
    tk.Label(w, text=m['desc'], font=('Segoe UI', 16, 'bold'), fg='white', bg='#e6007e').pack(pady=12)
root.after(4000, root.destroy); root.mainloop()
"""


def identificar_telas():
    mons = listar_monitores()
    if not mons:
        print("[tela] só funciona no Windows.")
        return
    print("[tela] mostrando o número em cada tela por 4 segundos...")
    try:
        subprocess.Popen([sys.executable, "-c", IDENTIFICAR, json.dumps(mons)])
    except Exception as e:
        print("[tela] não consegui mostrar os números:", e)


# ----------------------------------------------------------------------------- contagem de dedos
def _ang(a, b, c):
    """Ângulo (graus) no ponto b, formado por a-b-c, em 3D."""
    v1 = (a.x - b.x, a.y - b.y, a.z - b.z)
    v2 = (c.x - b.x, c.y - b.y, c.z - b.z)
    n1 = math.sqrt(sum(t * t for t in v1)) or 1e-9
    n2 = math.sqrt(sum(t * t for t in v2)) or 1e-9
    cos = max(-1.0, min(1.0, sum(p * q for p, q in zip(v1, v2)) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _dist(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def contar_dedos(w):
    """w = landmarks 3D em metros (world landmarks). Usa os ângulos das articulações,
    que não dependem da distância nem da rotação da mão."""
    dedos = 0
    # indicador, médio, anelar, mínimo: dedo esticado = articulações quase retas
    for mcp, pip, dip, tip in ((5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)):
        a_pip = _ang(w[mcp], w[pip], w[dip])
        a_dip = _ang(w[pip], w[dip], w[tip])
        longe = _dist(w[tip], w[0]) > _dist(w[pip], w[0]) * 1.1
        if a_pip > 150 and a_dip > 135 and longe:
            dedos += 1
    # polegar: reto e afastado da palma
    palma = _dist(w[0], w[9]) or 1e-6
    reto = _ang(w[2], w[3], w[4]) > 145 and _ang(w[1], w[2], w[3]) > 135
    afastado = _dist(w[4], w[9]) > palma * 0.80 and _dist(w[4], w[5]) > palma * 0.45
    if reto and afastado:
        dedos += 1
    return dedos


class Estabilizador:
    """Só muda o número quando ele se repete na maioria dos últimos quadros (evita piscar)."""

    def __init__(self, n=9, minimo=6):
        self.hist = collections.deque(maxlen=n)
        self.minimo = minimo
        self.valor = 0

    def add(self, v):
        self.hist.append(v)
        mais, qtd = collections.Counter(self.hist).most_common(1)[0]
        if qtd >= self.minimo:
            self.valor = mais
        return self.valor


# ----------------------------------------------------------------------------- câmera + mãos
def nomes_cameras():
    """Nomes das câmeras na mesma ordem que o OpenCV usa (DirectShow). Precisa do pacote pygrabber."""
    if os.name != "nt":
        return []
    try:
        from pygrabber.dshow_graph import FilterGraph
        return list(FilterGraph().get_input_devices())
    except Exception:
        return []


class Maos(threading.Thread):
    def __init__(self, cam_idx, janela):
        super().__init__(daemon=True)
        self.cam_idx = cam_idx
        self.janela = janela
        self.lock = threading.Lock()
        self.estado = {"hands": [], "fps": 0, "cam": "abrindo…"}
        self.preview = None
        self.rodando = True
        self.estab = {}
        self.janela_aberta = False
        self.pular = None                 # "modo" (imagem preta) ou "camera" (tecla C)
        self.modos = self.montar_modos()

    def montar_modos(self):
        """Jeitos de abrir cada câmera. Algumas webcams só mandam imagem num formato específico.
        Ordem das câmeras: a escolhida antes (tecla C) → webcams USB externas → câmera do notebook."""
        self.nomes = nomes_cameras()
        if self.cam_idx is not None:
            indices = [self.cam_idx]
        elif self.nomes:
            indices = list(range(len(self.nomes)))
            salvo = config.get("camera_nome")
            interna = lambda n: any(x in n.lower() for x in ("integrated", "internal", "built-in", "integrada", " ir ", "infrared",
                                                              "virtual", "obs", "hello", "front", "rear"))
            indices.sort(key=lambda i: (self.nomes[i] != salvo, interna(self.nomes[i])))
        else:
            indices = [0, 1, 2, 3]
        if os.name == "nt":
            jeitos = [(cv2.CAP_DSHOW, None, 640, 480, "DirectShow 640x480"),
                      (cv2.CAP_DSHOW, "MJPG", 1280, 720, "DirectShow 1280x720 MJPG"),
                      (cv2.CAP_MSMF, None, 640, 480, "Media Foundation 640x480"),
                      (cv2.CAP_DSHOW, "MJPG", 640, 480, "DirectShow 640x480 MJPG"),
                      (cv2.CAP_DSHOW, None, 1280, 720, "DirectShow 1280x720")]
        else:
            jeitos = [(cv2.CAP_ANY, None, 640, 480, "640x480")]
        return [(i,) + j for i in indices for j in jeitos]

    def abrir_camera(self, inicio=0):
        """Tenta os modos a partir de 'inicio' (dando a volta). Devolve (cap, posição) ou (None, None)."""
        modos = self.modos
        for k in range(len(modos)):
            pos = (inicio + k) % len(modos)
            i, api, fcc, w, h, nome = modos[pos]
            try:
                cap = cv2.VideoCapture(i, api)
            except Exception:
                continue
            if not cap.isOpened():
                cap.release()
                continue
            if fcc:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fcc))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_FPS, 30)
            frame = None
            for _ in range(30):                        # a câmera pode levar ~1 s para "acordar"
                ok, f = cap.read()
                if ok and f is not None and f.std() > 6:      # tem imagem de verdade (não é tela preta/cinza lisa)
                    frame = f
                    break
                time.sleep(0.05)
            if frame is not None:
                print(f"[câmera] usando: {self.nome(i)} · {nome} ({frame.shape[1]}x{frame.shape[0]})")
                return cap, pos
            print(f"[câmera] {self.nome(i)} · {nome}: sem imagem, tentando outro jeito...")
            cap.release()
        return None, None

    def nome(self, i):
        return self.nomes[i] if 0 <= i < len(self.nomes) else f"câmera {i}"

    def proxima_camera(self, pos):
        """Posição do primeiro modo da próxima câmera (para a tecla C)."""
        i = self.modos[pos][0]
        for k in range(1, len(self.modos) + 1):
            p = (pos + k) % len(self.modos)
            if self.modos[p][0] != i:
                return p
        return (pos + 1) % len(self.modos)

    def run(self):
        if os.name == "nt":
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    "Get-PnpDevice -Class Camera,Image -Status OK | ForEach-Object { $_.FriendlyName }"],
                                   capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                nomes = [x.strip() for x in r.stdout.splitlines() if x.strip()]
                if nomes:
                    print("[câmera] câmeras do Windows:", " | ".join(nomes))
            except Exception:
                pass
        if self.nomes:
            print("[câmera] câmeras encontradas:", " | ".join(f"{i}: {n}" for i, n in enumerate(self.nomes)))
        cap, pos = self.abrir_camera(0)
        avisou = False
        while cap is None and self.rodando:
            if not avisou:
                avisou = True
                print("[ERRO] Nenhuma câmera mandou imagem (vou continuar tentando a cada 3 s). Confira:")
                print("   • feche Teams, Zoom, o app Câmera do Windows e navegadores que estejam usando a câmera;")
                print("   • Configurações do Windows → Privacidade e segurança → Câmera → ligue")
                print("     'Acesso à câmera' e 'Permitir que aplicativos da área de trabalho acessem a câmera';")
                print("   • alguns notebooks têm tecla (F8, F10…) ou tampinha que desliga a câmera.")
                with self.lock:
                    self.estado["cam"] = "sem câmera — veja a janela preta"
            time.sleep(3)
            cap, pos = self.abrir_camera(0)
        idx = self.modos[pos][0] if cap is not None else None
        if cap is None:
            print("[ERRO] Nenhuma câmera mandou imagem. Confira:")
            print("   • feche Teams, Zoom, o app Câmera do Windows e navegadores que estejam usando a câmera;")
            print("   • Configurações do Windows → Privacidade e segurança → Câmera → ligue")
            print("     'Acesso à câmera' e 'Permitir que aplicativos da área de trabalho acessem a câmera';")
            print("   • alguns notebooks têm tecla (F8, F10…) ou tampinha que desliga a câmera.")
            with self.lock:
                self.estado["cam"] = "sem câmera"
            return
        with self.lock:
            self.estado["cam"] = self.nome(idx)
        try:
            hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1,
                                             min_detection_confidence=0.6, min_tracking_confidence=0.5)
        except Exception as e:
            print("\n[ERRO] A biblioteca de mãos não abriu:", e)
            if not mp.__file__.isascii():
                print("       Ela não funciona em pasta com acento (ex.: 'Área de Trabalho').")
                print("       Rode de novo o instalar.bat desta pasta — ele instala num lugar sem acento.\n")
            with self.lock:
                self.estado["cam"] = "erro na biblioteca de mãos"
            cap.release()
            return
        # rostos: para a NAI saber que alguém parou na frente da TV (até ~4–5 m)
        rostos = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.6)
        n_rostos, caixas, quadro_n = 0, [], 0
        desenho = mp.solutions.drawing_utils
        estilo = mp.solutions.drawing_styles
        t_fps, quadros, ultimo_prev = time.time(), 0, 0.0
        escuro_desde = None
        while self.rodando:
            if self.pular:
                motivo, self.pular = self.pular, None
                cap.release()
                inicio = self.proxima_camera(pos) if motivo == "camera" else (pos + 1) % len(self.modos)
                novo, npos = self.abrir_camera(inicio)
                if novo is None:
                    print("[câmera] nenhuma câmera com imagem; tentando de novo em 3 s...")
                    time.sleep(3)
                    self.pular = "modo"
                    continue
                cap, pos = novo, npos
                idx = self.modos[pos][0]
                escuro_desde = None
                if motivo == "camera" and self.nomes:                 # escolha manual fica salva
                    config["camera_nome"] = self.nome(idx)
                    salvar_config()
                with self.lock:
                    self.estado["cam"] = self.nome(idx)
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue
            if quadro_n % 10 == 0:                                       # imagem ficou preta? troca o jeito de abrir
                if frame.std() < 4:
                    escuro_desde = escuro_desde or time.time()
                    if time.time() - escuro_desde > 3:
                        print(f"[câmera] a imagem de {self.nome(idx)} ficou preta — tentando outro jeito/câmera...")
                        self.pular = "modo"
                        quadro_n += 1
                        continue
                else:
                    escuro_desde = None
            frame = cv2.flip(frame, 1)                                  # espelhado, como um espelho
            h, w = frame.shape[:2]
            esc = 640 / w if w > 640 else 1.0
            peq = cv2.resize(frame, (int(w * esc), int(h * esc))) if esc != 1.0 else frame
            rgb = cv2.cvtColor(peq, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)
            quadro_n += 1
            if quadro_n % 3 == 0:                                        # rosto: 1 a cada 3 quadros basta
                rf = rostos.process(rgb)
                caixas = [d.location_data.relative_bounding_box for d in (rf.detections or [])]
                caixas = [c for c in caixas if c.width >= ROSTO_MIN]
                n_rostos = len(caixas)
            maos = []
            if res.multi_hand_landmarks:
                for k, lm in enumerate(res.multi_hand_landmarks):
                    L = lm.landmark
                    wl = res.multi_hand_world_landmarks[k].landmark if res.multi_hand_world_landmarks else L
                    lado = res.multi_handedness[k].classification[0].label if res.multi_handedness else str(k)
                    bruto = contar_dedos(wl)
                    est = self.estab.setdefault(lado, Estabilizador())
                    xs = [p.x for p in L]
                    ys = [p.y for p in L]
                    maos.append({
                        "count": est.add(bruto), "raw": bruto,
                        "x": round(L[0].x, 4), "y": round(L[0].y, 4),
                        "tip": [round(L[8].x, 4), round(L[8].y, 4)],
                        "up": L[9].y < L[0].y,                         # dedos para cima
                        "size": round(max(max(xs) - min(xs), max(ys) - min(ys)), 4),
                    })
                    if self.janela or time.time() - ultimo_prev > 0.12:
                        desenho.draw_landmarks(peq, lm, mp.solutions.hands.HAND_CONNECTIONS,
                                               estilo.get_default_hand_landmarks_style(),
                                               estilo.get_default_hand_connections_style())
            # mãos que sumiram: zera o estabilizador
            if not maos:
                self.estab.clear()
            quadros += 1
            agora = time.time()
            if agora - t_fps >= 1:
                fps = quadros / (agora - t_fps)
                t_fps, quadros = agora, 0
            else:
                fps = self.estado.get("fps", 0)
            prev = None
            if agora - ultimo_prev > 0.12:                                   # prévia ~8 vezes por segundo
                ultimo_prev = agora
                mini = cv2.resize(peq, (320, int(320 * peq.shape[0] / peq.shape[1])))
                for c in caixas:
                    x0, y0 = int(c.xmin * 320), int(c.ymin * mini.shape[0])
                    cv2.rectangle(mini, (x0, y0), (x0 + int(c.width * 320), y0 + int(c.height * mini.shape[0])), (180, 120, 255), 2)
                for m in maos:
                    cv2.putText(mini, str(m["count"]), (int(m["x"] * 320) - 8, int(m["y"] * mini.shape[0]) + 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (110, 220, 60), 2)
                ok2, jpg = cv2.imencode(".jpg", mini, [cv2.IMWRITE_JPEG_QUALITY, 60])
                if ok2:
                    prev = "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()
            with self.lock:
                self.estado = {"hands": maos, "faces": n_rostos, "fps": round(fps, 1), "cam": self.nome(idx)}
                if prev:
                    self.preview = prev
            if not self.janela and self.janela_aberta:
                cv2.destroyAllWindows()
                self.janela_aberta = False
            if self.janela:
                self.janela_aberta = True
                for m in maos:
                    cv2.circle(peq, (int(m["tip"][0] * peq.shape[1]), int(m["tip"][1] * peq.shape[0])), 10, (110, 75, 255), -1)
                    cv2.putText(peq, f'{m["count"]} dedos', (int(m["x"] * peq.shape[1]) - 30, int(m["y"] * peq.shape[0]) + 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (60, 220, 110), 2)
                cv2.imshow("NAI - teste das maos (feche para sair)", peq)
                if cv2.waitKey(1) & 0xFF == 27:
                    self.janela = False
        cap.release()

    def pegar(self):
        with self.lock:
            e = dict(self.estado)
            e["img"], self.preview = self.preview, None
            return e


# ----------------------------------------------------------------------------- servidor WebSocket
clientes = set()


async def atender(ws, path=None):
    clientes.add(ws)
    print("[página] conectada")
    try:
        await ws.send(json.dumps(info_telas()))
        async for msg in ws:
            try:
                c = json.loads(msg)
            except Exception:
                continue
            if c.get("cmd") == "monitor":
                await asyncio.to_thread(mudar_tela, int(c.get("n", 1)))
                await ws.send(json.dumps(info_telas()))
            elif c.get("cmd") == "identify":
                identificar_telas()
    except Exception:
        pass
    finally:
        clientes.discard(ws)
        print("[página] desconectada")


def info_telas():
    return {"type": "info", "monitores": [{"n": m["n"], "desc": m["desc"]} for m in listar_monitores()],
            "monitor": config.get("monitor") or 1}


async def transmitir(maos):
    voltas = 0
    while True:
        voltas += 1
        if voltas % 75 == 0 and clientes:                                    # a cada ~3 s: lista de telas
            info = json.dumps(info_telas())
            for ws in list(clientes):
                try:
                    await ws.send(info)
                except Exception:
                    pass
        await asyncio.sleep(0.04)                                           # 25 vezes por segundo
        if not clientes:
            continue
        msg = json.dumps(maos.pegar())
        for ws in list(clientes):
            try:
                await ws.send(msg)
            except Exception:
                clientes.discard(ws)


# ----------------------------------------------------------------------------- abrir a página
def achar_html():
    for nome in ("NAI-IA-SENAI-Gama.html", "NAI-Cursos-SENAI-Gama.html", "NAI-Mundo-SENAI-Gama.html"):
        preferido = os.path.join(PASTA, nome)
        if os.path.exists(preferido):
            return preferido
    achados = sorted(glob.glob(os.path.join(PASTA, "*.html")))
    return achados[0] if achados else None


NAVEGADORES = {
    "firefox": [r"%ProgramFiles%\Mozilla Firefox\firefox.exe", r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
                r"%LocalAppData%\Mozilla Firefox\firefox.exe"],
    "edge":    [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"],
    "chrome":  [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe"],
}
NOMES_NAV = {"firefox": "Firefox", "edge": "Edge", "chrome": "Chrome"}
LINUX_NAV = {"firefox": "firefox", "edge": "msedge", "chrome": "google-chrome"}


def achar_exe(nome):
    for c in NAVEGADORES[nome]:
        c = os.path.expandvars(c)
        if os.path.exists(c):
            return c
    return shutil.which(LINUX_NAV[nome])


def navegadores_instalados():
    return [n for n in NAVEGADORES if achar_exe(n)]


def navegador_escolhido():
    """O escolhido (padrão: Firefox); se não estiver instalado, o primeiro que existir."""
    pref = config.get("navegador") or "firefox"
    for n in [pref] + [x for x in NAVEGADORES if x != pref]:
        exe = achar_exe(n)
        if exe:
            return n, exe
    return None, None


PREFS_FIREFOX = """
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
user_pref("media.navigator.permission.disabled", true);
user_pref("permissions.default.camera", 1);
user_pref("permissions.default.microphone", 1);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("trailhead.firstrun.didSeeAboutWelcome", true);
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("full-screen-api.warning.timeout", 0);
"""


def abrir_navegador(html):
    import pathlib
    url = pathlib.Path(html).resolve().as_uri() + "?kiosk=1"           # acentos e espaços do caminho já codificados
    nome, exe = navegador_escolhido()
    if not exe:
        import webbrowser
        print("[navegador] Firefox/Edge/Chrome não encontrado; abrindo o navegador padrão. Aperte F11 para tela cheia.")
        webbrowser.open(url)
        return
    m = monitor_escolhido()
    if nome == "firefox":
        perfil = os.path.join(tempfile.gettempdir(), "nai-quiosque-firefox")
        os.makedirs(perfil, exist_ok=True)
        with open(os.path.join(perfil, "user.js"), "w", encoding="utf-8") as f:
            f.write(PREFS_FIREFOX)
        args = [exe, "-no-remote", "-profile", perfil, "--kiosk", url]
    else:
        perfil = os.path.join(tempfile.gettempdir(), "nai-quiosque")
        args = [exe, "--kiosk", url, "--edge-kiosk-type=fullscreen", "--no-first-run", "--disable-features=Translate",
                "--autoplay-policy=no-user-gesture-required", "--hide-crash-restore-bubble",
                f"--user-data-dir={perfil}"]
        if m:
            args += [f"--window-position={m['x'] + 40},{m['y'] + 40}", "--window-size=800,600"]
    print(f"[navegador] abrindo em tela cheia no {NOMES_NAV[nome]}")
    navegador["proc"] = subprocess.Popen(args)
    if m:
        print(f"[tela] NAI na {m['desc']}")
        threading.Thread(target=encaixar_janela, args=(m, 15), daemon=True).start()   # confere e corrige a posição


def trocar_navegador():
    inst = navegadores_instalados()
    if not inst:
        print("[navegador] nenhum navegador encontrado.")
        return
    atual, _ = navegador_escolhido()
    prox = inst[(inst.index(atual) + 1) % len(inst)] if atual in inst else inst[0]
    config["navegador"] = prox
    salvar_config()
    print(f"[navegador] agora: {NOMES_NAV[prox]}  (instalados: {', '.join(NOMES_NAV[n] for n in inst)})")
    if navegador.get("html"):
        fechar_navegador()
        time.sleep(1)
        abrir_navegador(navegador["html"])


navegador = {"proc": None, "html": None}


def fechar_navegador():
    """Fecha só a janela da NAI (o Edge/Chrome aberto com o perfil 'nai-quiosque'), sem mexer em outros navegadores."""
    p = navegador.get("proc")
    if os.name == "nt":
        ps = ("Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'msedge.exe' -or $_.Name -eq 'chrome.exe' -or $_.Name -eq 'firefox.exe') "
              "-and $_.CommandLine -like '*nai-quiosque*' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        if p and p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    elif p and p.poll() is None:
        p.terminate()
    navegador["proc"] = None


MENU = """
==========================================================
   F  = FECHAR a NAI (tela cheia + este programa)
   R  = reabrir a tela da NAI
   T  = trocar a TELA (monitor) da NAI
   I  = identificar as telas (mostra o numero em cada uma)
   N  = trocar o NAVEGADOR (Firefox / Edge / Chrome)
   C  = trocar a CAMERA
   J  = mostrar/esconder a janela de teste da camera
==========================================================
"""


def sair(maos):
    print("\n[saindo] fechando a NAI...")
    fechar_navegador()
    maos.rodando = False
    time.sleep(0.4)
    os._exit(0)


def menu_teclado(maos):
    """Lê as teclas digitadas nesta janela (F, R, J)."""
    try:
        import msvcrt
        ler = lambda: msvcrt.getwch()
    except ImportError:
        ler = lambda: (sys.stdin.readline().strip() or " ")[0]
    print(MENU)
    while True:
        try:
            k = ler().lower()
        except Exception:
            return
        if k == "f":
            sair(maos)
        elif k == "r":
            if navegador.get("html"):
                print("[navegador] reabrindo a NAI...")
                fechar_navegador()
                time.sleep(1)
                abrir_navegador(navegador["html"])
            else:
                print("[aviso] a página não foi aberta por este programa.")
        elif k == "t":
            mons = listar_monitores()
            if not mons:
                print("[tela] só funciona no Windows.")
                continue
            atual = config.get("monitor") or 1
            print("\nTelas encontradas:")
            for m in mons:
                print("   ", m["desc"], " <- atual" if m["n"] == atual else "")
            print("Aperte o número da tela (ou outra tecla para cancelar): ", end="", flush=True)
            n = ler().strip()
            print(n)
            if n.isdigit():
                mudar_tela(int(n))
            else:
                print("[tela] cancelado.")
        elif k == "i":
            identificar_telas()
        elif k == "c":
            print("[câmera] trocando de câmera...")
            maos.pular = "camera"
        elif k == "n":
            trocar_navegador()
        elif k == "j":
            maos.janela = not maos.janela
            print("[teste] janela da câmera", "aberta (ESC fecha)" if maos.janela else "fechada")
        elif k in ("\r", "\n", " "):
            continue
        else:
            print(MENU)


def ao_fechar_console():
    """Se alguém fechar esta janela preta no X, fecha a tela da NAI junto."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        TIPO = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def tratar(evento):
            if evento in (2, 5, 6):                      # fechar janela, logoff, desligar
                fechar_navegador()
            return False
        ao_fechar_console.ref = TIPO(tratar)              # mantém a referência viva
        ctypes.windll.kernel32.SetConsoleCtrlHandler(ao_fechar_console.ref, True)
    except Exception:
        pass


# ----------------------------------------------------------------------------- principal
async def principal(a):
    maos = Maos(a.camera, a.janela)
    maos.start()
    async with websockets.serve(atender, "127.0.0.1", PORTA):
        print(f"[ok] mãos prontas em ws://127.0.0.1:{PORTA}")
        mons = listar_monitores()
        if len(mons) > 1:
            print("[tela] telas encontradas:", " | ".join(m["desc"] for m in mons))
        ao_fechar_console()
        if not a.sem_navegador:
            html = achar_html()
            navegador["html"] = html
            if html:
                abrir_navegador(html)
            else:
                print("[aviso] não achei o arquivo .html da NAI nesta pasta.")
        threading.Thread(target=menu_teclado, args=(maos,), daemon=True).start()
        await transmitir(maos)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="NAI – reconhecimento de mãos")
    p.add_argument("--camera", type=int, default=None, help="número da câmera (0, 1, 2…)")
    p.add_argument("--janela", action="store_true", help="mostra uma janela de teste com a câmera")
    p.add_argument("--monitor", type=int, default=None, help="número da tela onde a NAI abre (1, 2…)")
    p.add_argument("--navegador", choices=["firefox", "edge", "chrome"], default=None, help="navegador da NAI (padrão: firefox)")
    p.add_argument("--sem-navegador", action="store_true", help="não abre a página automaticamente")
    a = p.parse_args()
    if a.navegador:
        config["navegador"] = a.navegador
        salvar_config()
    if a.monitor:
        config["monitor"] = a.monitor
        salvar_config()
    print("NAI · Mundo SENAI — reconhecimento de mãos. Deixe esta janela aberta.\n")
    try:
        asyncio.run(principal(a))
    except KeyboardInterrupt:
        pass
    except OSError as e:
        print(f"\n[ERRO] Não consegui abrir a porta {PORTA}. O programa já está aberto em outra janela?\n", e)
        input("Aperte Enter para sair...")
