# PalScout.spec
# ------------------------------------------------
# PyInstaller build configuration. Using a .spec file instead of just
# a plain command line is more reliable for a multi-file project like
# this, since it lets us explicitly list "hidden imports" -- libraries
# that PyInstaller's automatic dependency scanner sometimes misses
# because they're imported conditionally (inside try/except blocks,
# like several of PalScout's optional AI provider SDKs).
#
# To build:
#   pyinstaller PalScout.spec
#
# Output goes to: dist/PalScout.exe

a = Analysis(
    ['bot.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # These are imported inside try/except blocks in ai_providers.py
        # and discord_bridge.py, so PyInstaller's automatic scan can
        # miss them -- listing them explicitly avoids a "module not
        # found" error at runtime that only shows up once the exe is
        # actually run, not at build time.
        'groq',
        'openai',
        'cerebras.cloud.sdk',
        'discord',
        'discord.ext.commands',
        'duckduckgo_search',
        'ddgs',
        'flask',
        'werkzeug',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PalScout',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # Keep a console window so the person running it
                    # can see log output (connection status, errors,
                    # chat activity) -- this is a server-side tool,
                    # not a GUI app, so a console window is expected
                    # and useful, not a bug.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='palscout_icon.ico',   # sets the .exe's file/taskbar icon --
                                 # without this, PyInstaller uses its
                                 # own generic default icon instead
)
