from pathlib import Path

from setuptools import Extension, setup

try:
    from Cython.Build import cythonize
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Cython is required to build native bindings") from exc

ROOT = Path(__file__).resolve().parent.parent

extensions = [
    Extension(
        name="pulsewave_11_native",
        language="c++",
        sources=[
            str(Path(__file__).resolve().parent / "pulsewave-11.pyx"),
            str(ROOT / "audio" / "audio_engine.cpp"),
            str(ROOT / "audio" / "decoder.cpp"),
            str(ROOT / "dsp" / "fft.cpp"),
            str(ROOT / "dsp" / "visualizer.cpp"),
        ],
        include_dirs=[str(ROOT / "audio"), str(ROOT / "dsp")],
    )
]

setup(
    name="pulsewave-11-native",
    ext_modules=cythonize(extensions, language_level=3),
)
