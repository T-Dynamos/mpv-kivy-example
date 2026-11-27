# mpv-kivy-example

Minimal standalone example demonstrating **`libmpv` (`0.42.0`)** hardware-accelerated video playback inside a **Kivy (`2.3.2`)** OpenGL / OpenGL ES widget on 
**Linux** and **Android (`arm64-v8a`)** using `python-for-android` local recipes.

<img width="805" height="610" alt="image" src="https://github.com/user-attachments/assets/9bef58e4-0b70-47c3-9edb-bc3af4d61e51" />

## Features

- **`libmpv 0.42.0`** built via `MesonRecipe(skip_python=True)` with `libmpv=true`, `egl-android=enabled`, `android-media-ndk=enabled`, and `opensles=enabled`.
- **`libplacebo 7.387.0`** with OpenGL ES + Vulkan 1.4 (`Vulkan-Headers v1.4.335`).
- **`libass 0.17.5`**, **`fribidi 1.0.18`**, **`harfbuzz`**, and **`ffmpeg`** (`--enable-jni --enable-mediacodec`).
- **Hardware decoding (`mediacodec-copy`)**: registers Android's `JavaVM*` with `libavcodec.av_jni_set_java_vm()` via `SDL_AndroidGetJNIEnv()`, and renders frames into a Kivy `Fbo` using `MpvRenderContext("opengl")` + `SDL_GL_GetProcAddress`.

## Project Structure

```text
.
├── main.py                      # Kivy MpvVideoWidget + player controls
├── mpvkivy.py                   # Linux/desktop SDL_GL_GetProcAddress monkey-patch for python-mpv
├── buildozer.spec               # Buildozer config (arm64-v8a, sdl2, local recipes)
├── assets/
│   └── sample.mp4               # Bundled 720p H.264/AAC test clip
└── p4alocalrecipes/
    ├── fribidi/__init__.py
    ├── harfbuzz/__init__.py
    ├── libass/__init__.py
    ├── libplacebo/__init__.py
    ├── libmpv/__init__.py       # Native libmpv.so (0.42.0) Meson recipe
    └── mpv/                     # python-mpv (1.0.8) PyProjectRecipe + Android patch
        ├── __init__.py
        └── android.patch
```

## Run on Linux

Requires system `libmpv` (e.g. `mpv` / `libmpv-dev`):

```bash
pip install kivy python-mpv
python main.py
```

## Build & Run (Android `arm64-v8a`)

```bash
buildozer android debug deploy run
```

> Note: `p4alocalrecipes/` assumes a `python-for-android` version that provides `MesonRecipe(skip_python=True)` (`kivy/python-for-android` `develop` branch).
