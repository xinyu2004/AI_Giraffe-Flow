#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace gf_fcm {

enum class FrameSourceKind { None, Synth, File, CarlaFile };

enum class PixelFormat { Rgb8, Nv12, Nv21, Yuv422, Yuv444 };

struct FrameMeta {
  std::uint32_t w{0};
  std::uint32_t h{0};
  std::uint32_t stride{0};  // RGB8 row stride after convert (w*3)
  std::uint64_t timestamp_ns{0};
  std::uint64_t seq{0};
  PixelFormat format{PixelFormat::Rgb8};
};

struct Frame {
  FrameMeta meta{};
  // Tightly packed RGB8 for stub/onnx heuristics (converted from tip format).
  std::vector<std::uint8_t> rgb;
};

FrameSourceKind ParseFrameSource(const char* env_or_null);

// Tip protocol (negotiate once + light per-frame meta):
//   GF_CARLA_FRAME_PATH = /path/to/frame.yuv   (neutral path; format not in suffix)
//   stream negotiate    = /path/to/frame.stream.json  {"format","w","h"}
//   per-frame meta      = /path/to/frame.meta.json    {"timestamp_ns","seq"}
// Legacy RGB: sidecar with w/h/stride still accepted.
class FrameSource {
 public:
  explicit FrameSource(FrameSourceKind kind);

  FrameSourceKind kind() const { return kind_; }

  // Returns a new frame when available (synth ticks / file seq or mtime change).
  std::optional<Frame> Poll();

  // Wall-clock ns (steady-ish via chrono).
  static std::uint64_t NowNs();

 private:
  FrameSourceKind kind_{FrameSourceKind::None};
  std::string plane_path_;
  std::string stream_path_;
  std::string meta_path_;
  std::string legacy_json_path_;
  bool negotiated_{false};
  PixelFormat negotiated_fmt_{PixelFormat::Nv12};
  std::uint32_t negotiated_w_{0};
  std::uint32_t negotiated_h_{0};
  std::uint64_t last_seq_{0};
  std::int64_t last_mtime_ns_{-1};
  std::uint64_t synth_seq_{0};
  std::uint64_t last_synth_ns_{0};
  std::uint32_t synth_period_ms_{50};

  bool EnsureNegotiated();
  std::optional<Frame> PollFile();
  std::optional<Frame> PollSynth();
  std::optional<Frame> PollLegacyRgb();
};

}  // namespace gf_fcm
