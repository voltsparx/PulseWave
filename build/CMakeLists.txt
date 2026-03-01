cmake_minimum_required(VERSION 3.16)
project(pulsewave_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(
    pulsewave_core
    ../native/audio/audio_engine.cpp
    ../native/audio/decoder.cpp
    ../native/dsp/fft.cpp
    ../native/dsp/visualizer.cpp
)

target_include_directories(
    pulsewave_core
    PUBLIC
    ../native/audio
    ../native/dsp
)

