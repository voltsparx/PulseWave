#pragma once

#include <vector>

namespace pulsewave {

std::vector<float> compute_fft_magnitude(const std::vector<float>& samples, int bins);

}  // namespace pulsewave

