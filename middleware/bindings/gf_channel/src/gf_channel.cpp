#include "gf_channel/gf_channel.h"

#include <atomic>
#include <cerrno>
#include <cstring>
#include <new>
#include <string>

#if defined(__linux__) || defined(__APPLE__)
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {

constexpr std::size_t kHdrAlign = 64;

#pragma pack(push, 1)
struct ChannelHeader {
  std::uint32_t magic{0};
  std::uint16_t version{0};
  std::uint16_t format{0};
  std::uint32_t w{0};
  std::uint32_t h{0};
  std::uint32_t plane_bytes{0};
  std::uint32_t buffers{0};
  std::uint32_t active{0};
  std::uint32_t ready{0};
  std::uint64_t seq{0};
  std::uint64_t timestamp_ns{0};
  std::uint8_t pad[32]{};
};
#pragma pack(pop)

static_assert(sizeof(ChannelHeader) <= kHdrAlign * 2, "ChannelHeader too large");

std::string PosixName(const char* slot) {
  std::string s = slot ? slot : "";
  for (char& c : s) {
    if (c == '.' || c == '/') {
      c = '_';
    }
  }
  if (s.empty()) {
    s = "gf_channel_anon";
  }
  if (s.front() != '/') {
    s.insert(s.begin(), '/');
  }
  if (s.size() > 200) {
    s.resize(200);
  }
  return s;
}

std::size_t MapBytes(std::uint32_t plane_bytes, std::uint32_t buffers) {
  const std::size_t hdr = ((sizeof(ChannelHeader) + kHdrAlign - 1) / kHdrAlign) * kHdrAlign;
  return hdr + static_cast<std::size_t>(plane_bytes) * buffers;
}

std::uint8_t* PlanePtr(ChannelHeader* hdr, std::uint32_t index) {
  const std::size_t hdr_bytes =
      ((sizeof(ChannelHeader) + kHdrAlign - 1) / kHdrAlign) * kHdrAlign;
  auto* base = reinterpret_cast<std::uint8_t*>(hdr) + hdr_bytes;
  return base + static_cast<std::size_t>(index) * hdr->plane_bytes;
}

}  // namespace

struct GfChannel {
  ChannelHeader* hdr{nullptr};
  void* map{nullptr};
  std::size_t map_bytes{0};
  int fd{-1};
  std::string posix_name;
  bool owner{false};
  std::uint64_t next_seq{1};
};

extern "C" uint32_t gf_channel_plane_bytes(uint16_t format, uint32_t w, uint32_t h) {
  if (format == GF_CHANNEL_FMT_BLOB) {
    /* w carries plane_bytes; h must be 1. */
    return (h == 1 && w > 0) ? w : 0;
  }
  if (w == 0 || h == 0) {
    return 0;
  }
  const std::uint64_t pixels = static_cast<std::uint64_t>(w) * h;
  switch (format) {
    case GF_CHANNEL_FMT_NV12:
    case GF_CHANNEL_FMT_NV21:
      return static_cast<uint32_t>(pixels + pixels / 2);
    case GF_CHANNEL_FMT_YUV422:
      return static_cast<uint32_t>(pixels * 2);
    case GF_CHANNEL_FMT_YUV444:
    case GF_CHANNEL_FMT_RGB8:
      return static_cast<uint32_t>(pixels * 3);
    default:
      return 0;
  }
}

extern "C" uint16_t gf_channel_format_from_name(const char* name) {
  if (!name || !name[0]) {
    return GF_CHANNEL_FMT_NV12;
  }
  if (std::strcmp(name, "nv12") == 0) {
    return GF_CHANNEL_FMT_NV12;
  }
  if (std::strcmp(name, "nv21") == 0) {
    return GF_CHANNEL_FMT_NV21;
  }
  if (std::strcmp(name, "yuv422") == 0) {
    return GF_CHANNEL_FMT_YUV422;
  }
  if (std::strcmp(name, "yuv444") == 0) {
    return GF_CHANNEL_FMT_YUV444;
  }
  if (std::strcmp(name, "rgb8") == 0) {
    return GF_CHANNEL_FMT_RGB8;
  }
  if (std::strcmp(name, "blob") == 0) {
    return GF_CHANNEL_FMT_BLOB;
  }
  return GF_CHANNEL_FMT_NV12;
}

extern "C" const char* gf_channel_format_name(uint16_t format) {
  switch (format) {
    case GF_CHANNEL_FMT_NV12:
      return "nv12";
    case GF_CHANNEL_FMT_NV21:
      return "nv21";
    case GF_CHANNEL_FMT_YUV422:
      return "yuv422";
    case GF_CHANNEL_FMT_YUV444:
      return "yuv444";
    case GF_CHANNEL_FMT_RGB8:
      return "rgb8";
    case GF_CHANNEL_FMT_BLOB:
      return "blob";
    default:
      return "nv12";
  }
}

#if !(defined(__linux__) || defined(__APPLE__))

extern "C" GfChannel* gf_channel_create(const char*, uint32_t, uint32_t, uint16_t,
                                       uint32_t) {
  errno = ENOTSUP;
  return nullptr;
}
extern "C" GfChannel* gf_channel_create_blob(const char*, uint32_t, uint32_t) {
  errno = ENOTSUP;
  return nullptr;
}
extern "C" GfChannel* gf_channel_open(const char*) {
  errno = ENOTSUP;
  return nullptr;
}
extern "C" void gf_channel_close(GfChannel*) {}
extern "C" int gf_channel_publish(GfChannel*, const void*, uint32_t, uint64_t,
                              uint64_t) {
  return -1;
}
extern "C" int gf_channel_latest(GfChannel*, void*, uint32_t, uint32_t*, uint64_t*,
                             uint64_t*, uint32_t*, uint32_t*, uint16_t*) {
  return -1;
}
extern "C" int gf_channel_info(const GfChannel*, uint32_t*, uint32_t*, uint16_t*,
                           uint32_t*, uint32_t*) {
  return -1;
}

#else

extern "C" GfChannel* gf_channel_create_blob(const char* slot, uint32_t plane_bytes,
                                            uint32_t buffers) {
  return gf_channel_create(slot, plane_bytes, 1u, GF_CHANNEL_FMT_BLOB, buffers);
}

extern "C" GfChannel* gf_channel_create(const char* slot, uint32_t w, uint32_t h,
                                       uint16_t format, uint32_t buffers) {
  if (buffers < 2 || buffers > GF_CHANNEL_MAX_BUFFERS) {
    errno = EINVAL;
    return nullptr;
  }
  const uint32_t plane = gf_channel_plane_bytes(format, w, h);
  if (plane == 0) {
    errno = EINVAL;
    return nullptr;
  }
  auto* ch = new (std::nothrow) GfChannel();
  if (!ch) {
    errno = ENOMEM;
    return nullptr;
  }
  ch->posix_name = PosixName(slot);
  ch->map_bytes = MapBytes(plane, buffers);
  ch->owner = true;

  ::shm_unlink(ch->posix_name.c_str());
  ch->fd = ::shm_open(ch->posix_name.c_str(), O_CREAT | O_RDWR | O_EXCL, 0600);
  if (ch->fd < 0) {
    delete ch;
    return nullptr;
  }
  if (::ftruncate(ch->fd, static_cast<off_t>(ch->map_bytes)) != 0) {
    const int e = errno;
    ::close(ch->fd);
    ::shm_unlink(ch->posix_name.c_str());
    delete ch;
    errno = e;
    return nullptr;
  }
  ch->map = ::mmap(nullptr, ch->map_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, ch->fd, 0);
  if (ch->map == MAP_FAILED) {
    const int e = errno;
    ::close(ch->fd);
    ::shm_unlink(ch->posix_name.c_str());
    delete ch;
    errno = e;
    return nullptr;
  }
  std::memset(ch->map, 0, ch->map_bytes);
  ch->hdr = static_cast<ChannelHeader*>(ch->map);
  ch->hdr->magic = GF_CHANNEL_MAGIC;
  ch->hdr->version = GF_CHANNEL_VERSION;
  ch->hdr->format = format;
  ch->hdr->w = w;
  ch->hdr->h = h;
  ch->hdr->plane_bytes = plane;
  ch->hdr->buffers = buffers;
  ch->hdr->active = 0;
  ch->hdr->seq = 0;
  ch->hdr->timestamp_ns = 0;
  std::atomic_thread_fence(std::memory_order_release);
  ch->hdr->ready = 1;
  return ch;
}

extern "C" GfChannel* gf_channel_open(const char* slot) {
  auto* ch = new (std::nothrow) GfChannel();
  if (!ch) {
    errno = ENOMEM;
    return nullptr;
  }
  ch->posix_name = PosixName(slot);
  ch->owner = false;
  ch->fd = ::shm_open(ch->posix_name.c_str(), O_RDWR, 0600);
  if (ch->fd < 0) {
    delete ch;
    return nullptr;
  }
  struct stat st {};
  if (::fstat(ch->fd, &st) != 0 || st.st_size <= 0) {
    const int e = errno;
    ::close(ch->fd);
    delete ch;
    errno = e ? e : EINVAL;
    return nullptr;
  }
  ch->map_bytes = static_cast<std::size_t>(st.st_size);
  ch->map = ::mmap(nullptr, ch->map_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, ch->fd, 0);
  if (ch->map == MAP_FAILED) {
    const int e = errno;
    ::close(ch->fd);
    delete ch;
    errno = e;
    return nullptr;
  }
  ch->hdr = static_cast<ChannelHeader*>(ch->map);
  if (ch->hdr->magic != GF_CHANNEL_MAGIC || ch->hdr->version != GF_CHANNEL_VERSION ||
      ch->hdr->ready == 0) {
    ::munmap(ch->map, ch->map_bytes);
    ::close(ch->fd);
    delete ch;
    errno = EINVAL;
    return nullptr;
  }
  return ch;
}

extern "C" void gf_channel_close(GfChannel* ch) {
  if (!ch) {
    return;
  }
  if (ch->map && ch->map != MAP_FAILED) {
    ::munmap(ch->map, ch->map_bytes);
  }
  if (ch->fd >= 0) {
    ::close(ch->fd);
  }
  if (ch->owner && !ch->posix_name.empty()) {
    ::shm_unlink(ch->posix_name.c_str());
  }
  delete ch;
}

extern "C" int gf_channel_publish(GfChannel* ch, const void* plane, uint32_t plane_bytes,
                              uint64_t timestamp_ns, uint64_t seq) {
  if (!ch || !ch->hdr || !plane) {
    errno = EINVAL;
    return -1;
  }
  if (plane_bytes != ch->hdr->plane_bytes) {
    errno = EINVAL;
    return -1;
  }
  const uint32_t nbuf = ch->hdr->buffers;
  if (nbuf < 2) {
    errno = EINVAL;
    return -1;
  }
  const uint32_t write_idx = (ch->hdr->active + 1u) % nbuf;
  std::memcpy(PlanePtr(ch->hdr, write_idx), plane, plane_bytes);
  std::atomic_thread_fence(std::memory_order_release);
  const uint64_t use_seq = seq ? seq : ch->next_seq++;
  if (seq) {
    ch->next_seq = seq + 1;
  }
  ch->hdr->timestamp_ns = timestamp_ns;
  ch->hdr->seq = use_seq;
  ch->hdr->active = write_idx;
  return 0;
}

extern "C" int gf_channel_latest(GfChannel* ch, void* plane_out, uint32_t plane_cap,
                             uint32_t* out_plane_bytes, uint64_t* inout_last_seq,
                             uint64_t* out_timestamp_ns, uint32_t* out_w, uint32_t* out_h,
                             uint16_t* out_format) {
  if (!ch || !ch->hdr || !plane_out || !inout_last_seq) {
    errno = EINVAL;
    return -1;
  }
  std::atomic_thread_fence(std::memory_order_acquire);
  const uint64_t seq = ch->hdr->seq;
  if (seq == 0 || seq == *inout_last_seq) {
    return 0;
  }
  const uint32_t idx = ch->hdr->active % ch->hdr->buffers;
  const uint32_t need = ch->hdr->plane_bytes;
  if (plane_cap < need) {
    errno = ENOMEM;
    return -1;
  }
  std::memcpy(plane_out, PlanePtr(ch->hdr, idx), need);
  std::atomic_thread_fence(std::memory_order_acquire);
  // Re-check seq did not change mid-copy (best-effort).
  if (ch->hdr->seq != seq || ch->hdr->active != idx) {
    return 0;
  }
  *inout_last_seq = seq;
  if (out_plane_bytes) {
    *out_plane_bytes = need;
  }
  if (out_timestamp_ns) {
    *out_timestamp_ns = ch->hdr->timestamp_ns;
  }
  if (out_w) {
    *out_w = ch->hdr->w;
  }
  if (out_h) {
    *out_h = ch->hdr->h;
  }
  if (out_format) {
    *out_format = ch->hdr->format;
  }
  return 1;
}

extern "C" int gf_channel_info(const GfChannel* ch, uint32_t* out_w, uint32_t* out_h,
                           uint16_t* out_format, uint32_t* out_plane_bytes,
                           uint32_t* out_buffers) {
  if (!ch || !ch->hdr) {
    errno = EINVAL;
    return -1;
  }
  if (out_w) {
    *out_w = ch->hdr->w;
  }
  if (out_h) {
    *out_h = ch->hdr->h;
  }
  if (out_format) {
    *out_format = ch->hdr->format;
  }
  if (out_plane_bytes) {
    *out_plane_bytes = ch->hdr->plane_bytes;
  }
  if (out_buffers) {
    *out_buffers = ch->hdr->buffers;
  }
  return 0;
}

#endif
