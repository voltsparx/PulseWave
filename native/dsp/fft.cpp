#include "fft.h"

#include <algorithm>
#include <cmath>

namespace pulsewave {

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

}  // namespace pulsewave
