# src/overlay/overlay.py
# ---------------------------------------------------------------------------
# Десктоп-оверлей Тето.
# Ловит рендер VTube Studio через Spout2 и рисует его прозрачным, поверх всех,
# click-through окном в правом нижнем углу основного монитора.
# VTS остаётся рендер-движком (трекинг/физика/эмоции-хоткеи НЕ трогаем).
# Окно — обычный WS-клиент хаба: шлёт логи и слушает команды {"type":"overlay"}.
#
#   pip install PySide6 glfw SpoutGL websockets
#
# В VTube Studio:
#   1) Настройки камеры -> Spout2 -> Enable/Start (сендер: VTubeStudioSpout)
#   2) Фон -> ColorPicker -> включить "Transparent in capture" (прозрачный фон)
# ---------------------------------------------------------------------------

import os
import sys
import json
import time
import array
import signal
import ctypes
import asyncio
import threading
from itertools import repeat

import glfw
import SpoutGL
import websockets
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, QObject, Signal

# на два уровня вверх, как остальные сервисы (на случай импорта hub_log)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# GL_RGBA как целочисленная константа (из самого SpoutGL, без PyOpenGL)
try:
    from SpoutGL.enums import GL_RGBA
except Exception:
    GL_RGBA = 0x1908

# ============================== НАСТРОЙКИ ==============================
HUB_URI     = "ws://localhost:8765"
SENDER_NAME = "VTubeStudioSpout"   # имя Spout-сендера от VTS (несколько окон VTS -> VTubeStudioSpout2 и т.д.)
OVERLAY_W   = 1000                  # ширина окна оверлея, px
OVERLAY_H   = 1180                  # высота окна оверлея, px
MARGIN      = 24                   # отступ от краёв экрана, px
FPS         = 60                   # частота опроса Spout
INVERT      = False                 # переворот по вертикали (GL -> экран). Если Тето вверх ногами — поставь False
# ======================================================================


def log(level, message):
    """Печать в консоль + лог-конверт в хаб (формат как у send_log: ts/level/message в data)."""
    print(f"[overlay] {message}", flush=True)
    HubClient.post_log(level, message)


# ------------------------------- SPOUT --------------------------------
class SpoutSource:
    """Приёмник Spout. grab() -> (rgba_bytes, w, h) или None.
    Требует ТЕКУЩИЙ GL-контекст в этом потоке (обеспечиваем через glfw перед вызовом)."""

    def __init__(self, sender_name):
        self.sender_name = sender_name
        self.receiver = SpoutGL.SpoutReceiver()
        self.receiver.setReceiverName(sender_name)
        self.buffer = None
        self.w = 0
        self.h = 0
        self._connected = None

    def grab(self):
        # заполняем текущий буфер (на первом вызове buffer=None — это нормально)
        self.receiver.receiveImage(self.buffer, GL_RGBA, INVERT, 0)

        # сендер подключился / сменил размер -> перевыделяем буфер; пиксели будут на СЛЕДУЮЩЕМ кадре
        if self.receiver.isUpdated():
            w = self.receiver.getSenderWidth()
            h = self.receiver.getSenderHeight()
            if w > 0 and h > 0:
                self.w, self.h = w, h
                self.buffer = array.array('B', repeat(0, w * h * 4))
            return None

        connected = self.receiver.isConnected()
        if connected != self._connected:
            self._connected = connected
            log("info", "VTS-сендер найден, Тето на экране" if connected
                        else f"VTS-сендер '{self.sender_name}' не виден (VTS запущен? Spout2 включён?)")

        if not connected or self.buffer is None or self.w == 0:
            return None
        return (bytes(self.buffer), self.w, self.h)

    def close(self):
        try:
            self.receiver.releaseReceiver()
        except Exception:
            pass


# ------------------------------- ОКНО ---------------------------------
class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, spout, gl_window):
        super().__init__()
        self.spout = spout
        self.gl_window = gl_window
        self._pixmap = None
        self._styles_applied = False

        # прозрачное, безрамочное, поверх всех, без иконки в панели задач, click-through
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput   # click-through на уровне Qt
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)     # per-pixel альфа
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.resize(OVERLAY_W, OVERLAY_H)
        self._move_to_corner()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(max(1, int(1000 / FPS)))

    def _move_to_corner(self):
        geo = QtWidgets.QApplication.primaryScreen().geometry()   # ВСЯ область монитора, включая панель задач
        x = geo.x() + geo.width() - self.width() - MARGIN         # справа, отступ MARGIN оставляем
        y = geo.y() + geo.height() - self.height()                # прижато к самому низу, без отступа
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._styles_applied:
            self._apply_win_styles()
            self._styles_applied = True

    def _apply_win_styles(self):
        # надёжный click-through + убрать из alt-tab/панели задач + не воровать фокус.
        # WS_EX_LAYERED специально НЕ трогаем — им управляет Qt (translucent window).
        GWL_EXSTYLE       = -20
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW  = 0x00000080
        WS_EX_NOACTIVATE  = 0x08000000
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        try:
            get_l, set_l = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
        except AttributeError:
            get_l, set_l = user32.GetWindowLongW, user32.SetWindowLongW
        ex = get_l(hwnd, GWL_EXSTYLE)
        ex |= WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        set_l(hwnd, GWL_EXSTYLE, ex)

    def _tick(self):
        # контекст должен быть текущим ИМЕННО перед обращением к Spout
        glfw.make_context_current(self.gl_window)
        frame = self.spout.grab()
        if frame is None:
            if self._pixmap is not None:      # сендер пропал — очищаем, чтобы не залипал старый кадр
                self._pixmap = None
                self.update()
            return
        data, w, h = frame
        # если по краям грязный ореол — поменяй на Format_RGBA8888_Premultiplied
        img = QtGui.QImage(data, w, h, w * 4, QtGui.QImage.Format_RGBA8888)
        pix = QtGui.QPixmap.fromImage(img)    # копирует; после этого data можно отпускать
        self._pixmap = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.update()

    def paintEvent(self, event):
        if self._pixmap is None:
            return
        p = QtGui.QPainter(self)
        x = (self.width() - self._pixmap.width()) // 2      # по центру горизонтально
        y = self.height() - self._pixmap.height()           # прижать к низу окна
        p.drawPixmap(x, y, self._pixmap)
        p.end()

    # --- команды с хаба: {"type":"overlay","data":{"action":"show|hide|toggle"}} ---
    def on_command(self, data):
        action = (data or {}).get("action", "")
        if action == "hide":
            self.hide()
            log("info", "оверлей скрыт по команде")
        elif action == "show":
            self.show()
            log("info", "оверлей показан по команде")
        elif action == "toggle":
            self.setVisible(not self.isVisible())
            log("info", f"оверлей {'показан' if self.isVisible() else 'скрыт'} (toggle)")
        # новые команды (масштаб, угол и т.п.) добавляются здесь так же


# ----------------------------- МОСТ / ХАБ -----------------------------
class SignalBridge(QObject):
    command = Signal(dict)   # эмитится из потока хаба, слот выполняется в GUI-потоке (queued)


class HubClient(threading.Thread):
    """WS-клиент хаба в своём потоке/цикле. Реконнект каждые 3 c (как веб-морда)."""
    _instance = None

    def __init__(self, uri, bridge):
        super().__init__(daemon=True)
        self.uri = uri
        self.bridge = bridge
        self.loop = None
        self._out = None                 # asyncio.Queue, создаётся внутри цикла
        HubClient._instance = self

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._out = asyncio.Queue()
        self.loop.run_until_complete(self._main())

    async def _main(self):
        while True:
            try:
                async with websockets.connect(self.uri) as ws:
                    await ws.send(json.dumps({
                        "type": "log", "sender": "overlay",
                        "data": {"ts": time.time(), "level": "info",
                                 "message": "оверлей подключён к хабу"},
                    }))
                    sender_task = asyncio.create_task(self._drain(ws))
                    try:
                        async for raw in ws:
                            try:
                                env = json.loads(raw)
                            except Exception:
                                continue
                            if env.get("type") == "overlay":
                                self.bridge.command.emit(env.get("data") or {})
                    finally:
                        sender_task.cancel()
            except Exception:
                pass  # хаб ещё не поднят или упал — молча ретраим
            await asyncio.sleep(3)

    async def _drain(self, ws):
        while True:
            env = await self._out.get()
            try:
                await ws.send(json.dumps(env))
            except Exception:
                pass

    @classmethod
    def post_log(cls, level, message):
        """Потокобезопасно кладём лог-конверт в очередь отправки (если цикл уже жив)."""
        inst = cls._instance
        if not inst or inst.loop is None or inst._out is None:
            return
        env = {"type": "log", "sender": "overlay",
               "data": {"ts": time.time(), "level": level, "message": message}}
        try:
            inst.loop.call_soon_threadsafe(inst._out.put_nowait, env)
        except Exception:
            pass


# ------------------------------- MAIN ---------------------------------
def main():
    # Ctrl+C в консоли гасит процесс (Qt сам не пропускает SIGINT в exec)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # заставляем Qt использовать настоящий desktop OpenGL (не ANGLE) — ставить ДО QApplication
    QtWidgets.QApplication.setAttribute(Qt.AA_UseDesktopOpenGL, True)

    # скрытое GLFW-окно — держатель GL-контекста для Spout (в главном потоке)
    if not glfw.init():
        print("[overlay] glfw.init() failed", flush=True)
        sys.exit(1)
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.FOCUSED, glfw.FALSE)
    gl_window = glfw.create_window(64, 64, "overlay-gl", None, None)
    if not gl_window:
        glfw.terminate()
        print("[overlay] glfw.create_window failed", flush=True)
        sys.exit(1)
    glfw.make_context_current(gl_window)

    app = QtWidgets.QApplication(sys.argv)

    spout = SpoutSource(SENDER_NAME)
    bridge = SignalBridge()
    window = OverlayWindow(spout, gl_window)
    bridge.command.connect(window.on_command)   # queued между потоками автоматически

    HubClient(HUB_URI, bridge).start()

    window.show()
    log("info", f"оверлей запущен, ждём сендер '{SENDER_NAME}'")

    try:
        app.exec()
    finally:
        spout.close()
        glfw.terminate()


if __name__ == "__main__":
    main()