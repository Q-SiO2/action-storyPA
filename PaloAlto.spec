# One-file presenter, editable JSON copied alongside by build.bat.
a = Analysis(['main.py'], pathex=[], binaries=[],
             datas=[('data/scenarios.json', 'data')],
             hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['pytest', 'fastapi', 'uvicorn', 'websockets'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='PaloAlto', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False)
