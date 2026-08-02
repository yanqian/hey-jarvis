from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs


ROOT = Path(SPEC).resolve().parents[2]
SITE = Path(__import__("site").getsitepackages()[0])
OWW = SITE / "openwakeword"
MODELS = OWW / "resources" / "models"
REALTIME_STATIC = ROOT / "src" / "realtime_host" / "static"

required_models = [
    MODELS / "melspectrogram.tflite",
    MODELS / "embedding_model.tflite",
    MODELS / "hey_jarvis_v0.1.tflite",
]
missing = [str(path) for path in required_models if not path.is_file()]
required_static = [
    REALTIME_STATIC / "index.html",
    REALTIME_STATIC / "app.js",
    REALTIME_STATIC / "styles.css",
]
missing.extend(str(path) for path in required_static if not path.is_file())
if missing:
    raise SystemExit("missing packaged runtime assets: " + ", ".join(missing))

datas = [
    (str(path), "openwakeword/resources/models") for path in required_models
]
datas.extend(
    (str(path), "src/realtime_host/static") for path in required_static
)
binaries = collect_dynamic_libs("ai_edge_litert")

a = Analysis(
    [str(ROOT / "app" / "sidecar" / "product_sidecar.py")],
    pathex=[str(ROOT), str(ROOT / "app" / "sidecar")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "ai_edge_litert.interpreter",
        "sounddevice",
        "_sounddevice",
    ],
    excludes=[
        "onnxruntime",
        "openai",
        "scipy",
        "sklearn",
        "webrtcvad",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hey-jarvis-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch="arm64",
    codesign_identity=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="hey-jarvis-sidecar",
)
