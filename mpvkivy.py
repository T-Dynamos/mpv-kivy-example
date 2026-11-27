"""Desktop/Linux compatibility helper for python-mpv with Kivy SDL2/SDL3."""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys

_GET_PROC_CB = None


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
    for soname in ("libSDL2-2.0.so.0", "libSDL2.so", "libSDL3.so.0", "libSDL3.so"):
        try:
            ctypes.CDLL(soname)
            return soname
        except OSError:
            continue
    return None


def sdl_opengl_init_params():
    """Return opengl_init_params dict backed by Kivy's SDL_GL_GetProcAddress."""
    global _GET_PROC_CB
    if _GET_PROC_CB is None:
        sdl_path = _find_sdl()
        if not sdl_path:
            raise RuntimeError("Could not locate libSDL2 or libSDL3 for OpenGL proc lookup")
        sdl = ctypes.CDLL(sdl_path)
        sdl.SDL_GL_GetProcAddress.argtypes = [ctypes.c_char_p]
        sdl.SDL_GL_GetProcAddress.restype = ctypes.c_void_p
        proc_t = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
        _GET_PROC_CB = proc_t(lambda _, name: sdl.SDL_GL_GetProcAddress(name))
    return {"get_proc_address": _GET_PROC_CB}


def patch(mpv_module):
    """Monkey-patch unpatched python-mpv on Linux to auto-fill opengl_init_params."""
    if hasattr(mpv_module, "sdl_opengl_init_params"):
        return

    orig_init = mpv_module.MpvRenderContext.__init__

    def _patched_init(self, mpv, api_type, *args, **kwargs):
        if api_type == "opengl" and "opengl_init_params" not in kwargs:
            kwargs["opengl_init_params"] = sdl_opengl_init_params()
        return orig_init(self, mpv, api_type, *args, **kwargs)

    mpv_module.sdl_opengl_init_params = sdl_opengl_init_params
    mpv_module.MpvRenderContext.__init__ = _patched_init
