# distutils: language = c++

from libcpp.vector cimport vector
from libcpp.string cimport string

cdef extern from "../audio/audio_engine.h" namespace "pulsewave_11":
    cdef cppclass AudioEngine:
        AudioEngine() except +
        bint init_audio()
        bint load_file(const string& path)
        bint play()
        bint pause()
        bint seek(double seconds)
        double get_position() const
        vector[float] get_waveform_chunk(int size) const

cdef extern from "../dsp/fft.h" namespace "pulsewave_11":
    vector[float] compute_fft_magnitude(const vector[float]& samples, int bins)
    vector[float] compute_signal_stats(const vector[float]& samples)

cdef AudioEngine _engine


def init_audio():
    return bool(_engine.init_audio())


def play_file(path: str):
    cdef string c_path = path.encode("utf-8")
    if not _engine.load_file(c_path):
        return False
    return bool(_engine.play())


def pause():
    return bool(_engine.pause())


def seek(seconds: float):
    return bool(_engine.seek(seconds))


def get_position():
    return float(_engine.get_position())


def get_visualizer_data(size: int = 64):
    cdef vector[float] raw = _engine.get_waveform_chunk(size)
    return [float(raw[i]) for i in range(raw.size())]


def compute_fft_bins(samples, bins: int):
    if bins <= 0:
        return []
    cdef vector[float] c_samples
    cdef double value
    for value in samples:
        c_samples.push_back(<float>value)
    cdef vector[float] out = compute_fft_magnitude(c_samples, bins)
    return [float(out[i]) for i in range(out.size())]


def compute_signal_stats(samples):
    cdef vector[float] c_samples
    cdef double value
    for value in samples:
        c_samples.push_back(<float>value)
    cdef vector[float] out = compute_signal_stats(c_samples)
    return [float(out[i]) for i in range(out.size())]
