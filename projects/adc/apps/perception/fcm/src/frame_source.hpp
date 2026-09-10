#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace gf_fcm {

enum class FrameSourceKind { None, Synth, File, CarlaFile, CameraShm };

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
  // Tightly packed RGB8 for stub/onnx heuristics (converted from camera format).
  std::vector<std::uint8_t> rgb;
};

FrameSourceKind ParseFrameSource(const char* env_or_null);

// Camera protocol:
//   GF_CHANNEL_TRANSPORT=shm → middleware/bindings/gf_channel (GF_CAMERA_SLOT)
//   GF_CHANNEL_TRANSPORT=file → plane + .stream.json + .meta.json (legacy)
class FrameSource {
 public:
  explicit FrameSource(FrameSourceKind kind);
  ~FrameSource();

  FrameSourceKind kind() const { return kind_; }

  // Returns a new frame when available (synth ticks / file seq / camera seq).
  std::optional<Frame> Poll();

  // Wall-clock ns (steady-ish via chrono).
  static std::uint64_t NowNs();

 private:
  FrameSourceKind kind_{FrameSourceKind::None};
  std::string plane_path_;
  std::string stream_path_;
  std::string meta_path_;
  std::string legacy_json_path_;
  std::string camera_slot_;
  void* camera_ch_{nullptr};  // GfChannel*
  bool negotiated_{false};
  PixelFormat negotiated_fmt_{PixelFormat::Nv12};
  std::uint32_t negotiated_w_{0};
  std::uint32_t negotiated_h_{0};
  std::uint64_t last_seq_{0};
  std::int64_t last_mtime_ns_{-1};
  std::uint64_t synth_seq_{0};
  std::uint64_t last_synth_ns_{0};
  std::uint32_t synth_period_ms_{50};
  std::vector<std::uint8_t> camera_plane_;

  bool EnsureNegotiated();
  bool EnsureCameraOpen();
  std::optional<Frame> PollFile();
  std::optional<Frame> PollCameraShm();
  std::optional<Frame> PollSynth();
  std::optional<Frame> PollLegacyRgb();
};

}  // namespace gf_fcm
