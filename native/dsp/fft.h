#pragma once

#include <vector>

namespace pulsewave_11 {

std::vector<float> compute_fft_magnitude(const std::vector<float>& samples, int bins);
std::vector<float> compute_signal_stats(const std::vector<float>& samples);

}  // namespace pulsewave_11
