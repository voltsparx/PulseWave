#pragma once

#include <string>
#include <vector>

namespace pulsewave_11 {

class AudioEngine {
public:
    bool init_audio();
    bool load_file(const std::string& path);
    bool play();
    bool pause();
    bool seek(double seconds);
    double get_position() const;
    std::vector<float> get_waveform_chunk(int size) const;

private:
    std::string current_file_;
    double position_seconds_ = 0.0;
    bool playing_ = false;
};

}  // namespace pulsewave_11
