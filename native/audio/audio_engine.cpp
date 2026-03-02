#include "audio_engine.h"

#include <cmath>

namespace pulsewave_11 {

bool AudioEngine::init_audio() {
    // Placeholder for PortAudio/FFmpeg initialization.
    return true;
}

bool AudioEngine::load_file(const std::string& path) {
    current_file_ = path;
    position_seconds_ = 0.0;
    playing_ = false;
    return !current_file_.empty();
}

bool AudioEngine::play() {
    if (current_file_.empty()) {
        return false;
    }
    playing_ = true;
    return true;
}

bool AudioEngine::pause() {
    playing_ = false;
    return true;
}

bool AudioEngine::seek(double seconds) {
    if (seconds < 0.0) {
        seconds = 0.0;
    }
    position_seconds_ = seconds;
    return true;
}

double AudioEngine::get_position() const {
    return position_seconds_;
}

std::vector<float> AudioEngine::get_waveform_chunk(int size) const {
    if (size <= 0) {
        return {};
    }
    std::vector<float> values;
    values.reserve(static_cast<size_t>(size));
    for (int i = 0; i < size; ++i) {
        const double x = position_seconds_ + static_cast<double>(i) / static_cast<double>(size);
        values.push_back(static_cast<float>(std::sin(x * 4.0)));
    }
    return values;
}

}  // namespace pulsewave_11
