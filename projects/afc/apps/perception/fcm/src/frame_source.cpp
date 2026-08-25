#include "frame_source.hpp"

#if __has_include("gf_gen/frame_ingest_config.hpp")
#include "gf_gen/frame_ingest_config.hpp"
#define GF_FCM_HAS_FRAME_INGEST 1
#endif

#if __has_include("gf_channel/gf_channel.h")
#include "gf_channel/gf_channel.h"
#define GF_FCM_HAS_GF_CHANNEL 1
#endif

#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <sys/stat.h>
#include <vector>

namespace gf_fcm {
namespace {

std::string EnvOr(const char* key, const char* def) {
  const char* v = std::getenv(key);
  return (v && v[0]) ? std::string(v) : std::string(def);
}

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

bool JsonStr(const std::string& js, const char* key, std::string* out) {
  const std::string pat = std::string("\"") + key + "\"";
  auto pos = js.find(pat);
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find(':', pos + pat.size());
  if (pos == std::string::npos) {
    return false;
  }
  pos = js.find('"', pos + 1);
  if (pos == std::string::npos) {
    return false;
  }
  const auto end = js.find('"', pos + 1);
  if (end == std::string::npos) {
    return false;
  }
  *out = js.substr(pos + 1, end - pos - 1);
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

PixelFormat ParsePixelFormat(const std::string& s) {
  if (s == "nv12") {
    return PixelFormat::Nv12;
  }
  if (s == "nv21") {
    return PixelFormat::Nv21;
  }
  if (s == "yuv422") {
    return PixelFormat::Yuv422;
  }
  if (s == "yuv444") {
    return PixelFormat::Yuv444;
  }
  if (s == "rgb8" || s == "rgb") {
    return PixelFormat::Rgb8;
  }
  return PixelFormat::Nv12;
}

std::size_t PlaneBytes(PixelFormat fmt, std::uint32_t w, std::uint32_t h) {
  switch (fmt) {
    case PixelFormat::Nv12:
    case PixelFormat::Nv21:
      return static_cast<std::size_t>(w) * h + (static_cast<std::size_t>(w) * h) / 2u;
    case PixelFormat::Yuv422:
      return static_cast<std::size_t>(w) * h * 2u;
    case PixelFormat::Yuv444:
    case PixelFormat::Rgb8:
      return static_cast<std::size_t>(w) * h * 3u;
  }
  return 0;
}

inline std::uint8_t Clamp8(int v) {
  if (v < 0) {
    return 0;
  }
  if (v > 255) {
    return 255;
  }
  return static_cast<std::uint8_t>(v);
}

void Nv12ToRgb(const std::uint8_t* yuv,
               std::uint32_t w,
               std::uint32_t h,
               bool swap_uv,
               std::vector<std::uint8_t>* rgb) {
  const std::size_t y_sz = static_cast<std::size_t>(w) * h;
  const std::uint8_t* y_plane = yuv;
  const std::uint8_t* uv = yuv + y_sz;
  rgb->assign(y_sz * 3u, 0);
  for (std::uint32_t y = 0; y < h; ++y) {
    for (std::uint32_t x = 0; x < w; ++x) {
      const int yv = y_plane[y * w + x];
      const std::size_t ui =
          static_cast<std::size_t>(y / 2u) * w + (x & ~1u);
      const int u = swap_uv ? uv[ui + 1] : uv[ui];
      const int v = swap_uv ? uv[ui] : uv[ui + 1];
      const int c = yv - 16;
      const int d = u - 128;
      const int e = v - 128;
      const std::size_t i = (static_cast<std::size_t>(y) * w + x) * 3u;
      (*rgb)[i + 0] = Clamp8((298 * c + 409 * e + 128) >> 8);
      (*rgb)[i + 1] = Clamp8((298 * c - 100 * d - 208 * e + 128) >> 8);
      (*rgb)[i + 2] = Clamp8((298 * c + 516 * d + 128) >> 8);
    }
  }
}

bool ConvertPlaneToRgb(PixelFormat fmt,
                       const std::vector<std::uint8_t>& plane,
                       std::uint32_t w,
                       std::uint32_t h,
                       std::vector<std::uint8_t>* rgb) {
  const std::size_t need = PlaneBytes(fmt, w, h);
  if (plane.size() < need || w == 0 || h == 0) {
    return false;
  }
  switch (fmt) {
    case PixelFormat::Rgb8:
      rgb->assign(plane.begin(), plane.begin() + static_cast<std::ptrdiff_t>(need));
      return true;
    case PixelFormat::Nv12:
      Nv12ToRgb(plane.data(), w, h, false, rgb);
      return true;
    case PixelFormat::Nv21:
      Nv12ToRgb(plane.data(), w, h, true, rgb);
      return true;
    case PixelFormat::Yuv422:
    case PixelFormat::Yuv444:
      // Stub path: use Y (first plane) as grayscale RGB.
      {
        const std::size_t n = static_cast<std::size_t>(w) * h;
        rgb->resize(n * 3u);
        for (std::size_t i = 0; i < n; ++i) {
          const std::uint8_t yv = plane[i];
          (*rgb)[i * 3u + 0] = yv;
          (*rgb)[i * 3u + 1] = yv;
          (*rgb)[i * 3u + 2] = yv;
        }
      }
      return true;
  }
  return false;
}

std::string ReadFile(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    return {};
  }
  std::ostringstream oss;
  oss << in.rdbuf();
  return oss.str();
}

std::string StemSibling(const std::string& path, const char* suffix) {
  // path stem + suffix (replay/file sidecar meta; not live GfChannel)
  const auto slash = path.find_last_of('/');
  const auto dot = path.find_last_of('.');
  std::string stem = path;
  if (dot != std::string::npos && (slash == std::string::npos || dot > slash)) {
    stem = path.substr(0, dot);
  }
  return stem + suffix;
}

}  // namespace

FrameSourceKind ParseFrameSource(const char* env_or_null) {
  const char* transport = std::getenv("GF_CHANNEL_TRANSPORT");
#if defined(GF_FCM_HAS_FRAME_INGEST)
  if (!transport || !transport[0]) {
    transport = gf_gen::frame_ingest::kCameraTransport;
  }
#endif
  const char* v = env_or_null;
  if (!v || !v[0]) {
    v = std::getenv("GF_FRAME_SOURCE");
  }
  if (!v || !v[0]) {
    v = std::getenv("GF_ACTIVE_SOURCE");  // secondary override
  }
#if defined(GF_FCM_HAS_FRAME_INGEST)
  // Prefer freeze active_source (isp|carla|…) over legacy kFrameSource IPC label.
  if (!v || !v[0]) {
    v = gf_gen::frame_ingest::kActiveSource;
  }
#endif
  std::string src = (v && v[0]) ? v : "none";
  if (src == "synth") {
    // FCM-internal color bars (no camera shm). Prefer GF_FRAME_SOURCE=colorbar + camera for product.
    return FrameSourceKind::Synth;
  }
  // Product live path: shm camera when transport says so.
  if (transport && std::strcmp(transport, "shm") == 0) {
    if (src != "none" && src != "file") {
      // isp|carla|replay|colorbar|carla_file → Open GfChannel
      return FrameSourceKind::CameraShm;
    }
  }
  if (src == "none") {
    return FrameSourceKind::None;
  }
  if (src == "file") {
    return FrameSourceKind::File;
  }
  if (src == "carla_file" || src == "carla" || src == "replay") {
    return FrameSourceKind::CarlaFile;
  }
  if (src == "isp" || src == "colorbar") {
    // No shm transport: cannot consume camera; idle.
    return FrameSourceKind::None;
  }
  std::cerr << "[ERROR] perception.fcm: unknown GF_FRAME_SOURCE=" << src
            << " (use none|isp|carla|replay|colorbar|file|carla_file|synth); "
               "falling back to none\n";
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
  if (kind_ == FrameSourceKind::CameraShm) {
#if defined(GF_FCM_HAS_FRAME_INGEST)
    camera_slot_ = EnvOr("GF_CAMERA_SLOT", gf_gen::frame_ingest::kCameraSlotFront);
#else
    camera_slot_ = EnvOr("GF_CAMERA_SLOT", "gf.channel.front");
#endif
    std::cout << "gf-perception-fcm: camera_transport=shm camera_slot=" << camera_slot_ << std::endl;
  }
  if (kind_ == FrameSourceKind::File || kind_ == FrameSourceKind::CarlaFile) {
#if defined(GF_FCM_HAS_FRAME_INGEST)
    plane_path_ = EnvOr("GF_CARLA_FRAME_PATH", gf_gen::frame_ingest::kFramePath);
#else
    plane_path_ = EnvOr("GF_CARLA_FRAME_PATH", "");
#endif
    if (plane_path_.empty()) {
      std::cerr << "[ERROR] perception.fcm: GF_FRAME_SOURCE needs GF_CARLA_FRAME_PATH\n";
    } else {
      stream_path_ = StemSibling(plane_path_, ".stream.json");
      meta_path_ = StemSibling(plane_path_, ".meta.json");
      legacy_json_path_ = StemSibling(plane_path_, ".json");
      if (plane_path_.size() > 4 &&
          plane_path_.compare(plane_path_.size() - 4, 4, ".rgb") == 0) {
        legacy_json_path_ =
            plane_path_.substr(0, plane_path_.size() - 4) + ".json";
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

FrameSource::~FrameSource() {
#if defined(GF_FCM_HAS_GF_CHANNEL)
  if (camera_ch_) {
    gf_channel_close(static_cast<GfChannel*>(camera_ch_));
    camera_ch_ = nullptr;
  }
#endif
}

bool FrameSource::EnsureNegotiated() {
  if (negotiated_) {
    return true;
  }
  const std::string js = ReadFile(stream_path_);
  if (js.empty()) {
    return false;
  }
  std::string fmt;
  std::uint32_t w = 0;
  std::uint32_t h = 0;
  if (!JsonStr(js, "format", &fmt) || !JsonU32(js, "w", &w) || !JsonU32(js, "h", &h)) {
    return false;
  }
  if (w == 0 || h == 0) {
    return false;
  }
#if defined(GF_FCM_HAS_FRAME_INGEST)
  // Prefer stream; warn if frozen pixel_format disagrees.
  if (std::strcmp(gf_gen::frame_ingest::kPixelFormat, fmt.c_str()) != 0) {
    std::cerr << "gf-perception-fcm: stream format=" << fmt
              << " != freeze kPixelFormat=" << gf_gen::frame_ingest::kPixelFormat
              << " (using stream)\n";
  }
#endif
  negotiated_fmt_ = ParsePixelFormat(fmt);
  negotiated_w_ = w;
  negotiated_h_ = h;
  negotiated_ = true;
  std::cout << "gf-perception-fcm: stream negotiate format=" << fmt << " "
            << w << "x" << h << std::endl;
  return true;
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
    case FrameSourceKind::CameraShm:
      return PollCameraShm();
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
  f.meta.format = PixelFormat::Rgb8;
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

std::optional<Frame> FrameSource::PollLegacyRgb() {
  if (legacy_json_path_.empty()) {
    return std::nullopt;
  }
  const std::string js = ReadFile(legacy_json_path_);
  if (js.empty()) {
    return std::nullopt;
  }
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
  meta.format = PixelFormat::Rgb8;

  const std::int64_t mtime = FileMtimeNs(legacy_json_path_);
  const bool seq_new = (meta.seq != 0 && meta.seq != last_seq_);
  const bool mtime_new = (mtime >= 0 && mtime != last_mtime_ns_);
  if (!seq_new && !mtime_new) {
    return std::nullopt;
  }
  if (meta.w == 0 || meta.h == 0 || meta.stride < meta.w * 3u) {
    return std::nullopt;
  }
  const std::size_t need = static_cast<std::size_t>(meta.stride) * meta.h;
  std::ifstream rin(plane_path_, std::ios::binary);
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

std::optional<Frame> FrameSource::PollFile() {
  if (plane_path_.empty()) {
    return std::nullopt;
  }
  if (!EnsureNegotiated()) {
    // Fall back to legacy RGB sidecar until stream appears.
    return PollLegacyRgb();
  }

  const std::string js = ReadFile(meta_path_);
  if (js.empty()) {
    return std::nullopt;
  }
  std::uint64_t timestamp_ns = 0;
  std::uint64_t seq = 0;
  if (!JsonU64(js, "timestamp_ns", &timestamp_ns)) {
    timestamp_ns = NowNs();
  }
  if (!JsonU64(js, "seq", &seq)) {
    seq = 0;
  }

  const std::int64_t mtime = FileMtimeNs(meta_path_);
  const bool seq_new = (seq != 0 && seq != last_seq_);
  const bool mtime_new = (mtime >= 0 && mtime != last_mtime_ns_);
  if (!seq_new && !mtime_new) {
    return std::nullopt;
  }

  const std::size_t need = PlaneBytes(negotiated_fmt_, negotiated_w_, negotiated_h_);
  std::ifstream rin(plane_path_, std::ios::binary);
  if (!rin) {
    return std::nullopt;
  }
  std::vector<std::uint8_t> plane(need);
  rin.read(reinterpret_cast<char*>(plane.data()),
           static_cast<std::streamsize>(need));
  if (static_cast<std::size_t>(rin.gcount()) < need) {
    return std::nullopt;
  }

  Frame f;
  f.meta.w = negotiated_w_;
  f.meta.h = negotiated_h_;
  f.meta.stride = negotiated_w_ * 3u;
  f.meta.timestamp_ns = timestamp_ns;
  f.meta.seq = seq;
  f.meta.format = negotiated_fmt_;
  if (!ConvertPlaneToRgb(negotiated_fmt_, plane, negotiated_w_, negotiated_h_,
                         &f.rgb)) {
    return std::nullopt;
  }
  last_seq_ = seq;
  last_mtime_ns_ = mtime;
  return f;
}

bool FrameSource::EnsureCameraOpen() {
#if defined(GF_FCM_HAS_GF_CHANNEL)
  if (camera_ch_) {
    return true;
  }
  camera_ch_ = gf_channel_open(camera_slot_.c_str());
  if (!camera_ch_) {
    return false;
  }
  std::uint32_t w = 0, h = 0, plane_bytes = 0, buffers = 0;
  std::uint16_t fmt = 0;
  if (gf_channel_info(static_cast<GfChannel*>(camera_ch_), &w, &h, &fmt, &plane_bytes,
                  &buffers) != 0) {
    return false;
  }
  negotiated_w_ = w;
  negotiated_h_ = h;
  negotiated_fmt_ = ParsePixelFormat(gf_channel_format_name(fmt));
  camera_plane_.resize(plane_bytes);
  negotiated_ = true;
  std::cout << "gf-perception-fcm: camera channel open " << camera_slot_ << " " << w
            << "x" << h << " " << gf_channel_format_name(fmt) << std::endl;
  return true;
#else
  (void)camera_slot_;
  return false;
#endif
}

std::optional<Frame> FrameSource::PollCameraShm() {
#if defined(GF_FCM_HAS_GF_CHANNEL)
  if (!EnsureCameraOpen()) {
    return std::nullopt;
  }
  std::uint32_t plane_bytes = 0;
  std::uint64_t ts = 0;
  std::uint32_t w = 0, h = 0;
  std::uint16_t fmt = 0;
  const int got = gf_channel_latest(
      static_cast<GfChannel*>(camera_ch_), camera_plane_.data(),
      static_cast<std::uint32_t>(camera_plane_.size()), &plane_bytes, &last_seq_, &ts,
      &w, &h, &fmt);
  if (got != 1) {
    return std::nullopt;
  }
  negotiated_w_ = w;
  negotiated_h_ = h;
  negotiated_fmt_ = ParsePixelFormat(gf_channel_format_name(fmt));
  Frame f;
  f.meta.w = w;
  f.meta.h = h;
  f.meta.stride = w * 3u;
  f.meta.timestamp_ns = ts;
  f.meta.seq = last_seq_;
  f.meta.format = negotiated_fmt_;
  if (!ConvertPlaneToRgb(negotiated_fmt_, camera_plane_, w, h, &f.rgb)) {
    return std::nullopt;
  }
  return f;
#else
  return std::nullopt;
#endif
}

}  // namespace gf_fcm
