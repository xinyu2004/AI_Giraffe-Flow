#include "frame_source.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_FCM_HAS_FRAME_INGEST 1
#endif

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <sys/stat.h>

namespace gf_fcm {
namespace {

std::string EnvOr(const char* key, const char* def) {
  const char* v = std::getenv(key);
  return (v && v[0]) ? std::string(v) : std::string(def);
}

// Minimal field extract: "key": number (int)
bool JsonU64(const std::string& js, const char* key, std::uint64_t* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  ++pos;
  while (pos < js.size() && (js[pos] == ' ' || js[pos] == '\t')) {
    ++pos;
  }
  char* end = nullptr;
  const unsigned long long v = std::strtoull(js.c_str() + pos, &end, 10);
  if (end == js.c_str() + pos) {
    return false;
  }
  *out = static_cast<std::uint64_t>(v);
  return true;
}

bool JsonU32(const std::string& js, const char* key, std::uint32_t* out) {
  std::uint64_t v = 0;
  if (!JsonU64(js, key, &v)) {
    return false;
  }
  *out = static_cast<std::uint32_t>(v);
  return true;
}

std::int64_t FileMtimeNs(const std::string& path) {
  struct stat st {};
  if (stat(path.c_str(), &st) != 0) {
    return -1;
  }
#if defined(__APPLE__)
  return static_cast<std::int64_t>(st.st_mtimespec.tv_sec) * 1000000000LL +
         st.st_mtimespec.tv_nsec;
#else
  return static_cast<std::int64_t>(st.st_mtim.tv_sec) * 1000000000LL +
         st.st_mtim.tv_nsec;
#endif
}

}  // namespace

FrameSourceKind ParseFrameSource(const char* env_or_null) {
  const char* v = env_or_null;
  if (!v || !v[0]) {
    v = std::getenv("GF_FRAME_SOURCE");
  }
#if defined(GF_FCM_HAS_FRAME_INGEST)
  // Compile-time freeze from req.frame_ingest; env is debug override only.
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kFrameSource;
  }
#endif
  if (!v || !v[0] || std::strcmp(v, "none") == 0) {
    return FrameSourceKind::None;
  }
  if (std::strcmp(v, "synth") == 0) {
    return FrameSourceKind::Synth;
  }
  if (std::strcmp(v, "file") == 0) {
    return FrameSourceKind::File;
  }
  if (std::strcmp(v, "carla_file") == 0) {
    return FrameSourceKind::CarlaFile;
  }
  std::cerr << "gf-perception-fcm: unknown GF_FRAME_SOURCE=" << v
            << " (use none|synth|file|carla_file); falling back to none\n";
  return FrameSourceKind::None;
}

std::uint64_t FrameSource::NowNs() {
  using clock = std::chrono::steady_clock;
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(
          clock::now().time_since_epoch())
          .count());
}

FrameSource::FrameSource(FrameSourceKind kind) : kind_(kind) {
  if (kind_ == FrameSourceKind::File || kind_ == FrameSourceKind::CarlaFile) {
#if defined(GF_FCM_HAS_FRAME_INGEST)
    rgb_path_ = EnvOr("GF_CARLA_FRAME_PATH", gf_gen::frame_ingest::kFramePath);
#else
    rgb_path_ = EnvOr("GF_CARLA_FRAME_PATH", "");
#endif
    if (rgb_path_.empty()) {
      std::cerr << "gf-perception-fcm: GF_FRAME_SOURCE needs "
                   "GF_CARLA_FRAME_PATH (raw RGB + .json sidecar)\n";
    } else {
      json_path_ = rgb_path_ + ".json";
      // Also accept foo.json next to foo.rgb when path ends with .rgb
      if (rgb_path_.size() > 4 &&
          rgb_path_.compare(rgb_path_.size() - 4, 4, ".rgb") == 0) {
        json_path_ = rgb_path_.substr(0, rgb_path_.size() - 4) + ".json";
      }
    }
  }
  if (kind_ == FrameSourceKind::Synth) {
    const char* p = std::getenv("GF_SYNTH_PERIOD_MS");
    if (p && p[0]) {
      synth_period_ms_ = static_cast<std::uint32_t>(std::strtoul(p, nullptr, 10));
      if (synth_period_ms_ == 0) {
        synth_period_ms_ = 50;
      }
    }
  }
}

std::optional<Frame> FrameSource::Poll() {
  switch (kind_) {
    case FrameSourceKind::None:
      return std::nullopt;
    case FrameSourceKind::Synth:
      return PollSynth();
    case FrameSourceKind::File:
    case FrameSourceKind::CarlaFile:
      return PollFile();
  }
  return std::nullopt;
}

std::optional<Frame> FrameSource::PollSynth() {
  const std::uint64_t now = NowNs();
  if (last_synth_ns_ != 0 &&
      (now - last_synth_ns_) <
          static_cast<std::uint64_t>(synth_period_ms_) * 1000000ULL) {
    return std::nullopt;
  }
  last_synth_ns_ = now;
  ++synth_seq_;

  constexpr std::uint32_t W = 320;
  constexpr std::uint32_t H = 240;
  constexpr std::uint32_t STRIDE = W * 3;
  Frame f;
  f.meta.w = W;
  f.meta.h = H;
  f.meta.stride = STRIDE;
  f.meta.timestamp_ns = now;
  f.meta.seq = synth_seq_;
  f.rgb.resize(static_cast<std::size_t>(STRIDE) * H);
  const std::uint8_t phase = static_cast<std::uint8_t>(synth_seq_ & 0xffu);
  for (std::uint32_t y = 0; y < H; ++y) {
    for (std::uint32_t x = 0; x < W; ++x) {
      const std::size_t i = static_cast<std::size_t>(y) * STRIDE + x * 3u;
      f.rgb[i + 0] = static_cast<std::uint8_t>((x + phase) & 0xffu);
      f.rgb[i + 1] = static_cast<std::uint8_t>((y + phase / 2) & 0xffu);
      f.rgb[i + 2] = static_cast<std::uint8_t>((x + y + phase) & 0xffu);
    }
  }
  return f;
}

std::optional<Frame> FrameSource::PollFile() {
  if (rgb_path_.empty() || json_path_.empty()) {
    return std::nullopt;
  }
  std::ifstream jin(json_path_);
  if (!jin) {
    return std::nullopt;
  }
  std::ostringstream oss;
  oss << jin.rdbuf();
  const std::string js = oss.str();

  FrameMeta meta{};
  if (!JsonU32(js, "w", &meta.w) || !JsonU32(js, "h", &meta.h)) {
    return std::nullopt;
  }
  if (!JsonU32(js, "stride", &meta.stride)) {
    meta.stride = meta.w * 3u;
  }
  if (!JsonU64(js, "timestamp_ns", &meta.timestamp_ns)) {
    meta.timestamp_ns = NowNs();
  }
  if (!JsonU64(js, "seq", &meta.seq)) {
    meta.seq = 0;
  }

  const std::int64_t mtime = FileMtimeNs(json_path_);
  const bool seq_new = (meta.seq != 0 && meta.seq != last_seq_);
  const bool mtime_new = (mtime >= 0 && mtime != last_mtime_ns_);
  if (!seq_new && !mtime_new) {
    return std::nullopt;
  }
  if (meta.w == 0 || meta.h == 0 || meta.stride < meta.w * 3u) {
    return std::nullopt;
  }

  const std::size_t need = static_cast<std::size_t>(meta.stride) * meta.h;
  std::ifstream rin(rgb_path_, std::ios::binary);
  if (!rin) {
    return std::nullopt;
  }
  Frame f;
  f.meta = meta;
  f.rgb.resize(need);
  rin.read(reinterpret_cast<char*>(f.rgb.data()),
           static_cast<std::streamsize>(need));
  if (static_cast<std::size_t>(rin.gcount()) < need) {
    return std::nullopt;
  }
  last_seq_ = meta.seq;
  last_mtime_ns_ = mtime;
  return f;
}

}  // namespace gf_fcm
