#pragma once

#include <string>
#include <vector>

namespace pulsewave_11 {

class Decoder {
public:
    bool open(const std::string& path);
    std::vector<float> read_samples(int frame_count);
    void close();

private:
    std::string path_;
};

}  // namespace pulsewave_11
