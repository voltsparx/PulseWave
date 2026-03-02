#include "visualizer.h"

#include <algorithm>

namespace pulsewave_11 {

std::vector<int> make_bar_heights(const std::vector<float>& magnitudes, int levels) {
    if (levels <= 0) {
        levels = 8;
    }
    if (magnitudes.empty()) {
        return {};
    }

    const float peak = std::max(0.0001f, *std::max_element(magnitudes.begin(), magnitudes.end()));
    std::vector<int> out;
    out.reserve(magnitudes.size());
    for (float value : magnitudes) {
        int level = static_cast<int>((value / peak) * static_cast<float>(levels - 1));
        level = std::max(0, std::min(levels - 1, level));
        out.push_back(level);
    }
    return out;
}

}  // namespace pulsewave_11
