# Minimal ARMv7 hard-float Linux cross toolchain (optional).
# Requires: sudo apt-get install -y g++-arm-linux-gnueabihf

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(GF_CROSS_PREFIX "arm-linux-gnueabihf" CACHE STRING "Cross compiler triplet")

set(CMAKE_C_COMPILER   "${GF_CROSS_PREFIX}-gcc")
set(CMAKE_CXX_COMPILER "${GF_CROSS_PREFIX}-g++")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
