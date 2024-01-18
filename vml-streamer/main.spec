# -*- mode: python ; coding: utf-8 -*-

images = [
    ('images/icon_first_frame.png', './images'),
    ('images/icon_last_frame.png', './images'),
    ('images/icon_play_pause.png', './images'),
    ('images/no_video.png', './images'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('./mediapipe_models/*', './mediapipe_models')],
    datas=images,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
splash = Splash(
    '../assets/images/vml_streamer_splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(180, 160),
    text_size=10,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name='vml_streamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
