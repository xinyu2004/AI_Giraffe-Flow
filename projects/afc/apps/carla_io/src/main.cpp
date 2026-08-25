// gf_carla_io — board/SIL cosim endpoint (C++).
// Listens for giraffe_client; publishes vehicle_state / fake_perc / camera to
// GfChannel; reads vehicle_cmd and sends back. No CARLA / no Python on board.

#include "gf_channel/gf_channel.h"
#include "gf_channel/boundary_pods.h"
#include "gf_channel/cosim_protocol.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

namespace {

volatile sig_atomic_t g_stop = 0;
void OnSig(int) { g_stop = 1; }

const char* EnvOr(const char* k, const char* fb) {
  const char* v = std::getenv(k);
  return (v && v[0]) ? v : fb;
}

int EnvInt(const char* k, int fb) {
  const char* v = std::getenv(k);
  if (!v || !v[0]) {
    return fb;
  }
  return std::atoi(v);
}

bool RecvAll(int fd, void* buf, std::size_t n) {
  auto* p = static_cast<std::uint8_t*>(buf);
  std::size_t got = 0;
  while (got < n && !g_stop) {
    const ssize_t r = ::recv(fd, p + got, n - got, 0);
    if (r == 0) {
      return false;
    }
    if (r < 0) {
      if (errno == EINTR) {
        continue;
      }
      if (errno == EAGAIN || errno == EWOULDBLOCK) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
        continue;
      }
      return false;
    }
    got += static_cast<std::size_t>(r);
  }
  return got == n;
}

bool SendAll(int fd, const void* buf, std::size_t n) {
  auto* p = static_cast<const std::uint8_t*>(buf);
  std::size_t sent = 0;
  while (sent < n && !g_stop) {
    const ssize_t r = ::send(fd, p + sent, n - sent, MSG_NOSIGNAL);
    if (r < 0) {
      if (errno == EINTR) {
        continue;
      }
      if (errno == EAGAIN || errno == EWOULDBLOCK) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
        continue;
      }
      return false;
    }
    sent += static_cast<std::size_t>(r);
  }
  return sent == n;
}

bool SendFrame(int fd, std::uint16_t type, std::uint64_t ts, std::uint64_t seq,
               const void* payload, std::uint32_t len) {
  GfCosimFrameHdr hdr{};
  hdr.magic = GF_COSIM_MAGIC;
  hdr.version = GF_COSIM_VERSION;
  hdr.msg_type = type;
  hdr.payload_len = len;
  hdr.timestamp_ns = ts;
  hdr.seq = seq;
  if (!SendAll(fd, &hdr, sizeof(hdr))) {
    return false;
  }
  if (len == 0) {
    return true;
  }
  return SendAll(fd, payload, len);
}

int ListenCosim(std::uint16_t port) {
  const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    return -1;
  }
  int yes = 1;
  ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    std::cerr << "[gf_carla_io] bind :" << port << " failed errno=" << errno << "\n";
    ::close(fd);
    return -1;
  }
  if (::listen(fd, 1) != 0) {
    ::close(fd);
    return -1;
  }
  // Non-blocking accept loop compatible with g_stop.
  const int flags = ::fcntl(fd, F_GETFL, 0);
  ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
  return fd;
}

int AcceptOne(int listen_fd) {
  while (!g_stop) {
    sockaddr_in peer{};
    socklen_t plen = sizeof(peer);
    const int c = ::accept(listen_fd, reinterpret_cast<sockaddr*>(&peer), &plen);
    if (c >= 0) {
      int yes = 1;
      ::setsockopt(c, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
      char ip[64];
      ::inet_ntop(AF_INET, &peer.sin_addr, ip, sizeof(ip));
      std::cout << "[gf_carla_io] giraffe_client connected from " << ip << ":"
                << ntohs(peer.sin_port) << "\n";
      return c;
    }
    if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
      return -1;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  return -1;
}

std::string SlotIdFromHdr(const GfCosimCameraHdr& ch) {
  char buf[GF_COSIM_SLOT_ID_LEN + 1];
  std::memcpy(buf, ch.slot_id, GF_COSIM_SLOT_ID_LEN);
  buf[GF_COSIM_SLOT_ID_LEN] = '\0';
  std::string id(buf);
  while (!id.empty() && (id.back() == '\0' || id.back() == ' ')) {
    id.pop_back();
  }
  return id;
}

GfChannel* EnsureCameraSlot(std::unordered_map<std::string, GfChannel*>* cams,
                            const std::string& id, std::uint32_t w, std::uint32_t h,
                            std::uint16_t fmt) {
  if (id.empty() || !cams) {
    return nullptr;
  }
  auto it = cams->find(id);
  if (it != cams->end() && it->second) {
    return it->second;
  }
  const std::string slot = "gf.channel." + id;
  GfChannel* ch = gf_channel_open(slot.c_str());
  if (!ch) {
    ch = gf_channel_create(slot.c_str(), w, h, fmt, 2);
    if (ch) {
      std::cout << "[gf_carla_io] created camera slot " << slot << " " << w << "x" << h
                << "\n";
    }
  } else {
    std::cout << "[gf_carla_io] opened camera slot " << slot << "\n";
  }
  if (ch) {
    (*cams)[id] = ch;
  }
  return ch;
}

}  // namespace

int main() {
  signal(SIGINT, OnSig);
  signal(SIGTERM, OnSig);

  const char* vs_slot = EnvOr("GF_VEHICLE_STATE_SLOT", "gf.channel.vehicle_state");
  const char* fp_slot = EnvOr("GF_FAKE_PERC_SLOT", "gf.channel.fake_perc");
  const char* cmd_slot = EnvOr("GF_VEHICLE_CMD_SLOT", "gf.channel.vehicle_cmd");
  const int port = EnvInt("GF_COSIM_PORT", static_cast<int>(GF_COSIM_DEFAULT_PORT));

  // Optional: pre-open front if ingest already Created it (AFC default).
  std::unordered_map<std::string, GfChannel*> cams;
  {
    const char* front = EnvOr("GF_CAMERA_SLOT", "gf.channel.front");
    GfChannel* cam = nullptr;
    for (int i = 0; i < 30 && !cam; ++i) {
      cam = gf_channel_open(front);
      if (!cam) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    }
    if (cam) {
      cams["front"] = cam;
      std::cout << "[gf_carla_io] pre-opened " << front << "\n";
    }
  }

  GfChannel* vs = gf_channel_create_blob(vs_slot, sizeof(GfVehicleStatePod), 2);
  GfChannel* fp = gf_channel_create_blob(fp_slot, sizeof(GfFakePercPod), 2);
  if (!vs || !fp) {
    std::cerr << "[ERROR] gf_carla_io: create vehicle_state/fake_perc failed\n";
    return 2;
  }

  GfChannel* cmd = nullptr;
  for (int i = 0; i < 50 && !cmd; ++i) {
    cmd = gf_channel_open(cmd_slot);
    if (!cmd) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  }
  if (!cmd) {
    std::cerr << "[WARN] gf_carla_io: vehicle_cmd open pending (gateway may start later)\n";
  }

  const int listen_fd = ListenCosim(static_cast<std::uint16_t>(port));
  if (listen_fd < 0) {
    return 3;
  }
  std::cout << "gf_carla_io: listen 0.0.0.0:" << port
            << " multi-cam (slot_id→gf.channel.<id>) vs=" << vs_slot << " fp=" << fp_slot
            << " cmd=" << cmd_slot << "\n";
  std::cout << "gf_carla_io: waiting for giraffe_client (truth+cameras+cmd cosim)\n";

  std::vector<std::uint8_t> payload;
  std::uint64_t cmd_seq_out = 0;
  std::uint64_t last_cmd_seen = 0;

  while (!g_stop) {
    const int cli = AcceptOne(listen_fd);
    if (cli < 0) {
      break;
    }

    {
      const int flags = ::fcntl(cli, F_GETFL, 0);
      ::fcntl(cli, F_SETFL, flags & ~O_NONBLOCK);
    }

    (void)SendFrame(cli, GF_COSIM_MSG_HELLO, 0, 0, nullptr, 0);

    while (!g_stop) {
      if (!cmd) {
        cmd = gf_channel_open(cmd_slot);
      }

      if (cmd) {
        GfVehicleCmdPod c{};
        std::uint32_t got = 0;
        std::uint64_t ts = 0;
        std::uint32_t ww = 0;
        std::uint32_t hh = 0;
        std::uint16_t fmt = 0;
        std::uint64_t seq = last_cmd_seen;
        if (gf_channel_latest(cmd, &c, sizeof(c), &got, &seq, &ts, &ww, &hh, &fmt) == 1 &&
            got >= sizeof(c) && c.magic == GF_CH_VEHICLE_CMD_MAGIC && seq != last_cmd_seen) {
          last_cmd_seen = seq;
          ++cmd_seq_out;
          if (!SendFrame(cli, GF_COSIM_MSG_VEHICLE_CMD, c.timestamp_ns, cmd_seq_out, &c,
                         sizeof(c))) {
            break;
          }
        }
      }

      pollfd pfd{};
      pfd.fd = cli;
      pfd.events = POLLIN;
      const int pr = ::poll(&pfd, 1, 20);
      if (pr < 0) {
        if (errno == EINTR) {
          continue;
        }
        break;
      }
      if (pr == 0 || !(pfd.revents & POLLIN)) {
        if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
          break;
        }
        continue;
      }

      GfCosimFrameHdr hdr{};
      if (!RecvAll(cli, &hdr, sizeof(hdr))) {
        std::cout << "[gf_carla_io] client disconnected\n";
        break;
      }
      if (hdr.magic != GF_COSIM_MAGIC || hdr.version != GF_COSIM_VERSION) {
        std::cerr << "[gf_carla_io] bad frame magic/version (need v"
                  << GF_COSIM_VERSION << ") — drop client\n";
        break;
      }
      if (hdr.payload_len > 16u * 1024u * 1024u) {
        std::cerr << "[gf_carla_io] payload too large\n";
        break;
      }
      payload.resize(hdr.payload_len);
      if (hdr.payload_len > 0 && !RecvAll(cli, payload.data(), hdr.payload_len)) {
        break;
      }

      switch (hdr.msg_type) {
        case GF_COSIM_MSG_HEARTBEAT:
        case GF_COSIM_MSG_HELLO:
          break;
        case GF_COSIM_MSG_VEHICLE_STATE:
          if (payload.size() >= sizeof(GfVehicleStatePod)) {
            const auto* st = reinterpret_cast<const GfVehicleStatePod*>(payload.data());
            if (st->magic == GF_CH_VEHICLE_STATE_MAGIC) {
              (void)gf_channel_publish(vs, st, sizeof(*st), hdr.timestamp_ns, hdr.seq);
            }
          }
          break;
        case GF_COSIM_MSG_FAKE_PERC:
          if (payload.size() >= sizeof(GfFakePercPod)) {
            const auto* p = reinterpret_cast<const GfFakePercPod*>(payload.data());
            if (p->magic == GF_CH_FAKE_PERC_MAGIC) {
              (void)gf_channel_publish(fp, p, sizeof(*p), hdr.timestamp_ns, hdr.seq);
            }
          }
          break;
        case GF_COSIM_MSG_CAMERA_NV12:
          if (payload.size() >= sizeof(GfCosimCameraHdr)) {
            GfCosimCameraHdr ch{};
            std::memcpy(&ch, payload.data(), sizeof(ch));
            const std::string id = SlotIdFromHdr(ch);
            const std::uint8_t* plane = payload.data() + sizeof(GfCosimCameraHdr);
            const std::uint32_t plane_len =
                static_cast<std::uint32_t>(payload.size() - sizeof(GfCosimCameraHdr));
            const std::uint32_t need =
                gf_channel_plane_bytes(ch.format, ch.width, ch.height);
            if (plane_len >= need && ch.format == GF_CHANNEL_FMT_NV12 && !id.empty()) {
              GfChannel* cam =
                  EnsureCameraSlot(&cams, id, ch.width, ch.height, ch.format);
              if (cam) {
                (void)gf_channel_publish(cam, plane, need, hdr.timestamp_ns, hdr.seq);
              }
            }
          }
          break;
        default:
          break;
      }
    }

    ::close(cli);
    if (!g_stop) {
      std::cout << "[gf_carla_io] waiting for giraffe_client reconnect…\n";
    }
  }

  ::close(listen_fd);
  for (auto& kv : cams) {
    if (kv.second) {
      gf_channel_close(kv.second);
    }
  }
  if (cmd) {
    gf_channel_close(cmd);
  }
  gf_channel_close(vs);
  gf_channel_close(fp);
  return 0;
}
