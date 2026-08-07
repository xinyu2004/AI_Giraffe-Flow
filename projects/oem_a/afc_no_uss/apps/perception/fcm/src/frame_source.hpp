#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace gf_fcm {

enum class FrameSourceKind { None, Synth, File, CarlaFile };

struct FrameMeta {
  std::uint32_t w{0};
  std::uint32_t h{0};
  std::uint32_t stride{0};
  std::uint64_t timestamp_ns{0};
  std::uint64_t seq{0};
};

struct Frame {
  FrameMeta meta{};
  std::vector<std::uint8_t> rgb;  // tightly packed RGB8, size >= stride * h
};

FrameSourceKind ParseFrameSource(const char* env_or_null);

// Shared tip protocol (wave B reader / wave C writer):
//   GF_CARLA_FRAME_PATH = /path/to/frame.rgb
//   sidecar            = /path/to/frame.json
//   {"w":W,"h":H,"stride":S,"timestamp_ns":T,"seq":N}
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
  std::string rgb_path_;
  std::string json_path_;
  std::uint64_t last_seq_{0};
  std::int64_t last_mtime_ns_{-1};
  std::uint64_t synth_seq_{0};
  std::uint64_t last_synth_ns_{0};
  std::uint32_t synth_period_ms_{50};

  std::optional<Frame> PollFile();
  std::optional<Frame> PollSynth();
};

}  // namespace gf_fcm
