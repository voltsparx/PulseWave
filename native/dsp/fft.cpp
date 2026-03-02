#include "fft.h"

#include <algorithm>
#include <cmath>

namespace pulsewave_11 {

std::vector<float> compute_fft_magnitude(const std::vector<float>& samples, int bins) {
    if (bins <= 0) {
        return {};
    }
    if (samples.empty()) {
        return std::vector<float>(static_cast<size_t>(bins), 0.0f);
    }

    std::vector<float> out(static_cast<size_t>(bins), 0.0f);
    const int chunk = std::max(1, static_cast<int>(samples.size()) / bins);
    for (int i = 0; i < bins; ++i) {
        const int begin = i * chunk;
        const int end = std::min(static_cast<int>(samples.size()), begin + chunk);
        float energy = 0.0f;
        int count = 0;
        for (int j = begin; j < end; ++j) {
            energy += samples[static_cast<size_t>(j)] * samples[static_cast<size_t>(j)];
            ++count;
        }
        if (count > 0) {
            out[static_cast<size_t>(i)] = std::sqrt(energy / static_cast<float>(count));
        }
    }
    return out;
}

std::vector<float> compute_signal_stats(const std::vector<float>& samples) {
    if (samples.empty()) {
        return {0.0f, 0.0f, 0.0f};
    }
    float peak = 0.0f;
    double energy = 0.0;
    for (float value : samples) {
        const float abs_value = std::abs(value);
        if (abs_value > peak) {
            peak = abs_value;
        }
        energy += static_cast<double>(value) * static_cast<double>(value);
    }
    const float rms = static_cast<float>(std::sqrt(energy / static_cast<double>(samples.size())));
    const float crest = rms > 0.000001f ? (peak / rms) : 0.0f;
    return {rms, peak, crest};
}

}  // namespace pulsewave_11
