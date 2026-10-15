# PyInstaller spec: `pyinstaller figma_to_pyside6.spec --noconfirm`
# Windows/Linux -> single-file executable, macOS -> .app bundle. Icon is chosen per platform.
import sys

NAME = "FigmaToPySide6"
ASSETS = "src/figma_to_pyside6/assets"
ICONS = {"win32": f"{ASSETS}/icon.ico", "darwin": f"{ASSETS}/icon.icns"}
icon = ICONS.get(sys.platform, f"{ASSETS}/icon.png")

a = Analysis(
    ["main.py"],
    pathex=["src"],
    datas=[(f"{ASSETS}/icon.png", "figma_to_pyside6/assets")],
    hiddenimports=[],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon,
        bundle_identifier="com.capgemini.figmatopyside6",
        info_plist={"NSHighResolutionCapable": True},
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=NAME,
        console=False,
        icon=icon,
        upx=False,
    )
