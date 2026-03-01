#include "decoder.h"

namespace pulsewave {

bool Decoder::open(const std::string& path) {
    path_ = path;
    return !path_.empty();
}

std::vector<float> Decoder::read_samples(int frame_count) {
    if (frame_count <= 0) {
        return {};
    }
    return std::vector<float>(static_cast<size_t>(frame_count), 0.0f);
}

void Decoder::close() {
    path_.clear();
}

}  // namespace pulsewave

