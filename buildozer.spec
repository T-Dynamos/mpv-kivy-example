[app]
title = MPV Kivy Example
package.name = mpvkivyexample
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,mp4
version = 0.1.0

requirements = python3,kivy==2.3.2,ffmpeg,mpv

orientation = landscape
fullscreen = 0

android.permissions = INTERNET
android.api = 36
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = True

p4a.bootstrap = sdl2
p4a.local_recipes = p4alocalrecipes
p4a.fork = kivy
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
