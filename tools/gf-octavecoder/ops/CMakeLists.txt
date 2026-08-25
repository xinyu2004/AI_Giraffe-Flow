# Header-only operators for Phase 1a (expand with .cpp sources later).
add_library(gf_octave_planning INTERFACE)
add_library(gf::octave_planning ALIAS gf_octave_planning)
target_include_directories(gf_octave_planning INTERFACE
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
)
target_compile_features(gf_octave_planning INTERFACE cxx_std_17)
