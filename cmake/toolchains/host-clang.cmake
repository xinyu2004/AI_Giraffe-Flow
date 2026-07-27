# Host Clang toolchain for SIL (P2.5).
# Prefer a separate build dir so GCC/Clang caches do not mix:
#
#   GF_SIL_TOOLCHAIN_FILE=cmake/toolchains/host-clang.cmake \
#     GF_BUILD_DIR=$PWD/build-clang \
#     bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh
#
# Or without this file:
#   GF_CC=clang GF_CXX=clang++ GF_BUILD_DIR=$PWD/build-clang bash …/compile_sil.sh
#
# Rebuild host deps with the same compilers (or isolate via GF_DEPS_PREFIX):
#   GF_CC=clang GF_CXX=clang++ GF_DEPS_PREFIX=$PWD/middleware/.deps-prefix-clang \
#     bash scripts/bootstrap_deps.sh

set(CMAKE_C_COMPILER "clang")
set(CMAKE_CXX_COMPILER "clang++")
