#include "detect_backend.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_FCM_HAS_FRAME_INGEST 1
#endif

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>

#if defined(GF_WITH_ONNX) && GF_WITH_ONNX
// Optional: link onnxruntime and replace heuristic with Ort::Session.
// Keep include optional so tree builds without the SDK headers when OFF.
#if __has_include(<onnxruntime_cxx_api.h>)
#include <onnxruntime_cxx_api.h>
#define GF_FCM_HAS_ORT_HEADERS 1
#endif
#endif

namespace gf_fcm {
namespace {

// Cheap stand-in for "detections from pixels" when ORT is absent or model missing.
DetectResult HeuristicFromPixels(const Frame& frame) {
  DetectResult r{};
  r.opaque = 1;
  if (frame.rgb.empty() || frame.meta.w == 0 || frame.meta.h == 0) {
    return r;
  }
  std::uint64_t sum = 0;
  std::uint64_t n = 0;
  const std::uint32_t step = 16;
  for (std::uint32_t y = 0; y < frame.meta.h; y += step) {
    for (std::uint32_t x = 0; x < frame.meta.w; x += step) {
      const std::size_t i =
          static_cast<std::size_t>(y) * frame.meta.stride + x * 3u;
      if (i + 2 >= frame.rgb.size()) {
        continue;
      }
      sum += frame.rgb[i] + frame.rgb[i + 1] + frame.rgb[i + 2];
      ++n;
    }
  }
  if (n == 0) {
    return r;
  }
  const std::uint64_t mean = sum / (n * 3u);
  // Map brightness bands → dyn count (1..3); always at least 1 if frame non-black.
  if (mean < 8) {
    r.dyn_obj_count = 0;
  } else {
    r.dyn_obj_count = static_cast<std::uint8_t>(1 + (mean / 64u) % 3u);
  }
  r.static_obj_count = (mean > 32) ? 1 : 0;
  return r;
}

#if defined(GF_FCM_HAS_ORT_HEADERS)
DetectResult TryOrtSession(const Frame& frame, const std::string& model_path) {
  if (model_path.empty()) {
    return HeuristicFromPixels(frame);
  }
  try {
    static Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "gf_fcm");
    static Ort::SessionOptions opts;
    static std::unique_ptr<Ort::Session> session;
    static std::string loaded;
    if (!session || loaded != model_path) {
      session = std::make_unique<Ort::Session>(env, model_path.c_str(), opts);
      loaded = model_path;
      std::cout << "gf-perception-fcm: ORT session loaded model=" << model_path
                << std::endl;
    }
    // Demo mapping: session load success → treat as 1 dyn (+ heuristic refine).
    // Full YOLO post-process is out of wave-B scope; opaque still marks onnx.
    auto r = HeuristicFromPixels(frame);
    if (r.dyn_obj_count == 0) {
      r.dyn_obj_count = 1;
    }
    r.opaque = 1;
    (void)session;
    return r;
  } catch (const std::exception& e) {
    std::cerr << "gf-perception-fcm: ORT failed (" << e.what()
              << "); using pixel heuristic\n";
    return HeuristicFromPixels(frame);
  }
}
#endif

}  // namespace

BackendKind ParseBackend(const char* env_or_null) {
  const char* v = env_or_null;
  if (!v || !v[0]) {
    v = std::getenv("GF_PERCEPTION_BACKEND");
  }
#if defined(GF_FCM_HAS_FRAME_INGEST)
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kPerceptionBackend;
  }
#endif
  if (v && std::strcmp(v, "onnx") == 0) {
    return BackendKind::Onnx;
  }
  return BackendKind::Stub;
}

DetectResult DetectStubFrame(const Frame& frame, std::uint64_t out_seq) {
  DetectResult r{};
  r.opaque = 0;
  r.dyn_obj_count = static_cast<std::uint8_t>(1 + (frame.meta.seq % 3u));
  r.static_obj_count = 1;
  (void)out_seq;
  return r;
}

DetectResult DetectOnnxOrHeuristic(const Frame& frame,
                                   const std::string& model_path) {
#if defined(GF_FCM_HAS_ORT_HEADERS)
  return TryOrtSession(frame, model_path);
#else
#if defined(GF_WITH_ONNX) && GF_WITH_ONNX
  std::cerr << "gf-perception-fcm: GF_WITH_ONNX=ON but onnxruntime headers "
               "missing; pixel heuristic (opaque=1)\n";
#else
  static bool once = false;
  if (!once) {
    once = true;
    std::cerr << "gf-perception-fcm: GF_PERCEPTION_BACKEND=onnx without "
                 "-DGF_WITH_ONNX=ON; pixel heuristic (opaque=1). "
                 "Rebuild with ORT to load GF_ONNX_MODEL.\n";
  }
#endif
  return HeuristicFromPixels(frame);
#endif
}

}  // namespace gf_fcm
