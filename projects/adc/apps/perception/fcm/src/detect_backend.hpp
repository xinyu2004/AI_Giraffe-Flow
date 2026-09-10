#pragma once

#include "frame_source.hpp"

#include <cstdint>
#include <string>

namespace gf_fcm {

enum class BackendKind { Stub, Onnx };

struct DetectResult {
  std::uint8_t dyn_obj_count{0};
  std::uint8_t static_obj_count{0};
  std::uint8_t opaque{0};  // 0=stub, 1=onnx (or onnx-heuristic)
};

BackendKind ParseBackend(const char* env_or_null);

// Frame-driven stub: non-zero dyn from frame content / seq (not EgoMotion).
DetectResult DetectStubFrame(const Frame& frame, std::uint64_t out_seq);

// Optional ORT path (compile with -DGF_WITH_ONNX=ON). Without ORT linked,
// falls back to a cheap pixel heuristic and still tags opaque=1 so the
// GF_PERCEPTION_BACKEND=onnx mapping path is exercisable in SIL.
DetectResult DetectOnnxOrHeuristic(const Frame& frame, const std::string& model_path);

}  // namespace gf_fcm
