from __future__ import annotations

import os
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

if not hasattr(mpv, "sdl_opengl_init_params"):
    import mpvkivy

    mpvkivy.patch(mpv)


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
        self._player = mpv.MPV(
            vo="libmpv",
            hwdec="auto",
            loop_file="inf",
            loglevel="warn",
        )
        self._ctx = mpv.MpvRenderContext(
            self._player,
            "opengl",
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
        sample = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "assets", "sample.mp4")
        )

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
