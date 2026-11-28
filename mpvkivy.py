"""Desktop/Linux compatibility helper for python-mpv with Kivy SDL2/SDL3/GLX/EGL."""

from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import sys

from kivy.logger import Logger

_GET_PROC_CB = None


def _sdl_search_order():
    if "kivy.core.window.window_sdl3" in sys.modules:
        return ("SDL3", "SDL2")
    if "kivy.core.window.window_sdl2" in sys.modules:
        return ("SDL2", "SDL3")
    return ("SDL3", "SDL2")


def _find_sdl():
    order = _sdl_search_order()
    patterns = {
        "SDL3": ("libSDL3-*.so*",),
        "SDL2": ("libSDL2-*.so*",),
    }
    sonames = {
        "SDL3": ("libSDL3.so.0", "libSDL3.so"),
        "SDL2": ("libSDL2-2.0.so.0", "libSDL2.so"),
    }

    # Search site-packages (Kivy.libs / kivy.libs) first
    for p in sys.path:
        for libs_dir in ("Kivy.libs", "kivy.libs"):
            d = os.path.join(p, libs_dir)
            if os.path.isdir(d):
                for name in order:
                    for pat in patterns[name]:
                        for f in glob.glob(os.path.join(d, pat)):
                            bn = os.path.basename(f)
                            if "ttf" not in bn and "mix" not in bn and "image" not in bn:
                                return f

    # Fall back to system libraries
    for name in order:
        found = ctypes.util.find_library(name)
        if found:
            return found
    for name in order:
        for soname in sonames[name]:
            try:
                ctypes.CDLL(soname)
                return soname
            except OSError:
                continue
    return None


def _resolve_get_proc_fn():
    sdl_path = _find_sdl()
    if sdl_path:
        sdl = ctypes.CDLL(sdl_path)
        get_ctx = getattr(sdl, "SDL_GL_GetCurrentContext", None)
        get_proc = getattr(sdl, "SDL_GL_GetProcAddress", None)
        if get_ctx is not None and get_proc is not None:
            get_ctx.restype = ctypes.c_void_p
            if get_ctx():
                get_proc.argtypes = [ctypes.c_char_p]
                get_proc.restype = ctypes.c_void_p
                Logger.info(f"mpvkivy: using SDL GL proc lookup from {sdl_path}")
                return get_proc

    for gl_name in ("libGL.so.1", "libGL.so"):
        try:
            gl = ctypes.CDLL(gl_name)
        except OSError:
            continue
        get_ctx = getattr(gl, "glXGetCurrentContext", None)
        get_proc = getattr(gl, "glXGetProcAddress", None) or getattr(
            gl, "glXGetProcAddressARB", None
        )
        if get_ctx is not None and get_proc is not None:
            get_ctx.restype = ctypes.c_void_p
            if get_ctx():
                get_proc.argtypes = [ctypes.c_char_p]
                get_proc.restype = ctypes.c_void_p
                Logger.info(f"mpvkivy: using GLX proc lookup from {gl_name}")
                return get_proc

    for egl_name in ("libEGL.so.1", "libEGL.so"):
        try:
            egl = ctypes.CDLL(egl_name)
        except OSError:
            continue
        get_ctx = getattr(egl, "eglGetCurrentContext", None)
        get_proc = getattr(egl, "eglGetProcAddress", None)
        if get_ctx is not None and get_proc is not None:
            get_ctx.restype = ctypes.c_void_p
            if get_ctx():
                get_proc.argtypes = [ctypes.c_char_p]
                get_proc.restype = ctypes.c_void_p
                Logger.info(f"mpvkivy: using EGL proc lookup from {egl_name}")
                return get_proc

    raise RuntimeError("Could not locate an active SDL, GLX, or EGL OpenGL context")


def sdl_opengl_init_params():
    """Return opengl_init_params dict backed by the active OpenGL proc lookup."""
    global _GET_PROC_CB
    if _GET_PROC_CB is None:
        get_proc = _resolve_get_proc_fn()
        proc_t = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
        _GET_PROC_CB = proc_t(lambda _, name: get_proc(name))
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
