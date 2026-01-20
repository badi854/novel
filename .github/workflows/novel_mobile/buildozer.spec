[app]

# App 名称
title = NovelMobile
package.name = novelmobile
package.domain = org.example

# 源码目录（buildozer 默认把 main.py 所在目录作为入口）
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json,txt,md
source.exclude_dirs = __pycache__,.git,.idea,build,dist

# 依赖（按你给的文章思路）：python3 + kivy
# 说明：后续如果要把 DOCX/PDF/EPUB 也带上，再逐个把库加入 requirements。
requirements = python3,kivy

# 运行入口
entrypoint = main.py

# Android 设置
orientation = portrait
fullscreen = 0

# Android 版本与架构（更稳的默认值）
android.minapi = 21
android.api = 33
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

# 权限：先给基础读写，便于调试导出；后续上架需要按 Scoped Storage 进一步收敛
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# 打包版本
version = 0.1.0

[buildozer]
log_level = 2


