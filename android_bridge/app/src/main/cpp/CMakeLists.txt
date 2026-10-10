cmake_minimum_required(VERSION 3.18.1)

project("npubridge_asr")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -frtti -fexceptions")

# SNPE headers are copied into inc/zdl by scripts/copy_whisper_assets.ps1
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/inc/)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/inc/zdl)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/inc/hpp)

# Whisper encoder (SNPE, Hexagon DSP/HTP) + mel preprocessing + token decoding.
# Adapted from qidk NLPSolution3-AutomaticSpeechRecognition-Whisper.
add_library(ASR SHARED native-lib_pre_post.cpp inference.cpp inference_helper.cpp decoder.cpp)

find_library(log-lib log)
find_library(android-lib android)

target_link_libraries(ASR
        ${log-lib}
        ${android-lib}
        ${CMAKE_CURRENT_SOURCE_DIR}/../jniLibs/arm64-v8a/libSNPE.so)
