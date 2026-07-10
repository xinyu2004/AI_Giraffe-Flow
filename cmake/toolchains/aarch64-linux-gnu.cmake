# Minimal aarch64 Linux cross toolchain (P0).
# Requires: sudo apt-get install -y g++-aarch64-linux-gnu
#
#   cmake -B build-aarch64 -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/aarch64-linux-gnu.cmake
#   cmake --build build-aarch64 -j$(nproc)

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(GF_CROSS_PREFIX "aarch64-linux-gnu" CACHE STRING "Cross compiler triplet")

set(CMAKE_C_COMPILER   "${GF_CROSS_PREFIX}-gcc")
set(CMAKE_CXX_COMPILER "${GF_CROSS_PREFIX}-g++")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
