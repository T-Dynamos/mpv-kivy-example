from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Fbo, Rectangle
from kivy.graphics.opengl import (
    GL_ACTIVE_TEXTURE,
    GL_BLEND,
    GL_FRAMEBUFFER_BINDING,
    GL_SCISSOR_TEST,
    GL_VIEWPORT,
    glActiveTexture,
    glBindFramebuffer,
    glDisable,
    glEnable,
    glGetIntegerv,
    glIsEnabled,
    glViewport,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget

import mpv


def _find_sdl():
    for p in sys.path:
        d = os.path.join(p, "kivy.libs")
        if os.path.isdir(d):
            for pat in ("libSDL3-*.so*", "libSDL2-*.so*"):
                for f in glob.glob(os.path.join(d, pat)):
                    bn = os.path.basename(f)
                    if "ttf" not in bn and "mix" not in bn and "image" not in bn:
                        return f
    for name in ("SDL3", "SDL2"):
        found = ctypes.util.find_library(name)
        if found:
            return found
    for soname in ("libSDL2.so", "libSDL3.so"):
        try:
            ctypes.CDLL(soname)
            return soname
        except OSError:
            continue
    return None


_sdl = ctypes.CDLL(_find_sdl())
_sdl.SDL_GL_GetProcAddress.argtypes = [ctypes.c_char_p]
_sdl.SDL_GL_GetProcAddress.restype = ctypes.c_void_p

_GLPROC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)


def _get_proc(_, name):
    return _sdl.SDL_GL_GetProcAddress(name)


_get_proc_c = _GLPROC(_get_proc)
_android_jvm_registered = False


def ensure_android_java_vm():
    """Register Android's JavaVM with FFmpeg so MediaCodec hardware decoding works."""
    global _android_jvm_registered
    if _android_jvm_registered or sys.platform != "android":
        return
    _android_jvm_registered = True
    try:
        _sdl.SDL_AndroidGetJNIEnv.restype = ctypes.c_void_p
        jni_env = _sdl.SDL_AndroidGetJNIEnv()
        if not jni_env:
            return
        fn_table = ctypes.cast(
            jni_env, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_java_vm = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )(fn_table[219])
        java_vm = ctypes.c_void_p()
        if get_java_vm(jni_env, ctypes.byref(java_vm)) == 0 and java_vm.value:
            libavcodec = ctypes.CDLL("libavcodec.so")
            libavcodec.av_jni_set_java_vm.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            libavcodec.av_jni_set_java_vm.restype = ctypes.c_int
            libavcodec.av_jni_set_java_vm(java_vm, None)
    except Exception:
        pass


class MpvVideoWidget(Widget):
    """Kivy widget rendering libmpv output into an OpenGL ES Fbo."""

    def __init__(self, video_path: str, on_status=None, **kwargs):
        super().__init__(**kwargs)
        self.video_path = video_path
        self.on_status = on_status
        self._player: mpv.MPV | None = None
        self._ctx: mpv.MpvRenderContext | None = None
        self._fbo: Fbo | None = None
        self._needs_render = threading.Event()

        with self.canvas:
            Color(1, 1, 1, 1)
            self._rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self._update_rect, size=self._update_rect)
        Clock.schedule_once(self._init_mpv, 0)
        Clock.schedule_interval(self._tick, 0)

    def _update_rect(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size
        w, h = max(1, int(self.width)), max(1, int(self.height))
        if self._fbo is None or self._fbo.size != (w, h):
            self._fbo = Fbo(size=(w, h))
            self._rect.texture = self._fbo.texture
            self._needs_render.set()

    def _init_mpv(self, _dt):
        ensure_android_java_vm()
        self._player = mpv.MPV(
            vo="libmpv",
            hwdec="auto",
            loop_file="inf",
            loglevel="warn",
        )
        self._ctx = mpv.MpvRenderContext(
            self._player,
            "opengl",
            opengl_init_params={"get_proc_address": _get_proc_c},
            advanced_control=True,
        )
        self._ctx.update_cb = self._needs_render.set
        self._update_rect()
        self._player.play(self.video_path)

    def _tick(self, _dt):
        if self._ctx is None or self._fbo is None:
            return
        if not self._needs_render.is_set() and not self._ctx.update():
            return
        self._needs_render.clear()

        prev_fbo = int(glGetIntegerv(GL_FRAMEBUFFER_BINDING)[0])
        prev_vp = glGetIntegerv(GL_VIEWPORT)
        prev_active_tex = int(glGetIntegerv(GL_ACTIVE_TEXTURE)[0])
        was_scissor = bool(glIsEnabled(GL_SCISSOR_TEST))
        was_blend = bool(glIsEnabled(GL_BLEND))

        w, h = self._fbo.size
        self._fbo.bind()
        fbo_id = int(glGetIntegerv(GL_FRAMEBUFFER_BINDING)[0])
        self._ctx.render(
            flip_y=False,
            opengl_fbo={"w": int(w), "h": int(h), "fbo": fbo_id},
        )
        self._fbo.release()

        glBindFramebuffer(36160, prev_fbo)
        glViewport(*prev_vp)
        glActiveTexture(prev_active_tex)
        (glEnable if was_scissor else glDisable)(GL_SCISSOR_TEST)
        (glEnable if was_blend else glDisable)(GL_BLEND)
        self.canvas.ask_update()

        if self.on_status and self._player is not None:
            self.on_status(self._player)

    def toggle_pause(self):
        if self._player is not None:
            self._player.pause = not self._player.pause

    def seek_ratio(self, ratio: float):
        if self._player is not None and self._player.duration:
            self._player.seek(ratio * self._player.duration, reference="absolute")

    def close(self):
        if self._ctx is not None:
            self._ctx.free()
            self._ctx = None
        if self._player is not None:
            self._player.terminate()
            self._player = None


class MpvExampleApp(App):
    def build(self):
        root = BoxLayout(orientation="vertical", spacing=8, padding=8)
        sample = os.path.abspath(os.path.join("assets", "sample.mp4"))

        self.status_lbl = Label(text="Initializing libmpv...", size_hint_y=None, height=40)
        self.video = MpvVideoWidget(sample, on_status=self._update_status)

        controls = BoxLayout(size_hint_y=None, height=56, spacing=8)
        play_btn = Button(text="Play / Pause", size_hint_x=None, width=160)
        play_btn.bind(on_release=lambda *_: self.video.toggle_pause())
        self.slider = Slider(min=0.0, max=1.0, value=0.0)
        self.slider.bind(on_touch_up=self._on_seek)
        controls.add_widget(play_btn)
        controls.add_widget(self.slider)

        root.add_widget(self.status_lbl)
        root.add_widget(self.video)
        root.add_widget(controls)
        return root

    def _on_seek(self, slider, touch):
        if slider.collide_point(*touch.pos):
            self.video.seek_ratio(slider.value)

    def _update_status(self, player):
        hwdec = player.hwdec_current or "software"
        pos = player.time_pos or 0.0
        dur = player.duration or 0.0
        params = player.video_params or {}
        res = f"{params.get('w', '?')}x{params.get('h', '?')}"
        state = "paused" if player.pause else "playing"
        self.status_lbl.text = f"{res} | hwdec={hwdec} | {state} | {pos:.1f}s / {dur:.1f}s"
        if dur > 0:
            self.slider.value = min(1.0, max(0.0, pos / dur))

    def on_stop(self):
        self.video.close()


if __name__ == "__main__":
    MpvExampleApp().run()
