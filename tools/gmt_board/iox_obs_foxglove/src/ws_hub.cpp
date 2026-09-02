#include "gf_foxglove/ws_hub.hpp"

#include "gf_foxglove/png.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
#include <string_view>
#include <vector>

namespace gf_foxglove {
namespace {

// --- SHA-1 (RFC 3174), for WebSocket accept ---
void sha1(const std::uint8_t* msg, std::size_t n, std::uint8_t out[20]) {
  std::uint32_t h0 = 0x67452301u, h1 = 0xEFCDAB89u, h2 = 0x98BADCFEu, h3 = 0x10325476u,
                h4 = 0xC3D2E1F0u;
  std::vector<std::uint8_t> buf(msg, msg + n);
  buf.push_back(0x80);
  while ((buf.size() % 64) != 56) buf.push_back(0);
  std::uint64_t bits = static_cast<std::uint64_t>(n) * 8;
  for (int i = 7; i >= 0; --i) buf.push_back(static_cast<std::uint8_t>((bits >> (i * 8)) & 0xff));

  auto rol = [](std::uint32_t v, int s) { return (v << s) | (v >> (32 - s)); };
  for (std::size_t off = 0; off < buf.size(); off += 64) {
    std::uint32_t w[80];
    for (int i = 0; i < 16; ++i) {
      w[i] = (static_cast<std::uint32_t>(buf[off + i * 4]) << 24) |
             (static_cast<std::uint32_t>(buf[off + i * 4 + 1]) << 16) |
             (static_cast<std::uint32_t>(buf[off + i * 4 + 2]) << 8) |
             static_cast<std::uint32_t>(buf[off + i * 4 + 3]);
    }
    for (int i = 16; i < 80; ++i) w[i] = rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    std::uint32_t a = h0, b = h1, c = h2, d = h3, e = h4;
    for (int i = 0; i < 80; ++i) {
      std::uint32_t f, k;
      if (i < 20) {
        f = (b & c) | ((~b) & d);
        k = 0x5A827999u;
      } else if (i < 40) {
        f = b ^ c ^ d;
        k = 0x6ED9EBA1u;
      } else if (i < 60) {
        f = (b & c) | (b & d) | (c & d);
        k = 0x8F1BBCDCu;
      } else {
        f = b ^ c ^ d;
        k = 0xCA62C1D6u;
      }
      std::uint32_t t = rol(a, 5) + f + e + k + w[i];
      e = d;
      d = c;
      c = rol(b, 30);
      b = a;
      a = t;
    }
    h0 += a;
    h1 += b;
    h2 += c;
    h3 += d;
    h4 += e;
  }
  auto put = [&](int i, std::uint32_t v) {
    out[i] = static_cast<std::uint8_t>((v >> 24) & 0xff);
    out[i + 1] = static_cast<std::uint8_t>((v >> 16) & 0xff);
    out[i + 2] = static_cast<std::uint8_t>((v >> 8) & 0xff);
    out[i + 3] = static_cast<std::uint8_t>(v & 0xff);
  };
  put(0, h0);
  put(4, h1);
  put(8, h2);
  put(12, h3);
  put(16, h4);
}

std::string ws_accept_key(const std::string& key) {
  const char* guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
  std::string src = key + guid;
  std::uint8_t dig[20];
  sha1(reinterpret_cast<const std::uint8_t*>(src.data()), src.size(), dig);
  return b64_encode(dig, 20);
}

std::string ws_frame(int opcode, const void* payload, std::size_t n) {
  std::string h;
  h.push_back(static_cast<char>(0x80 | (opcode & 0x0f)));
  if (n < 126) {
    h.push_back(static_cast<char>(n));
  } else if (n < (1u << 16)) {
    h.push_back(126);
    h.push_back(static_cast<char>((n >> 8) & 0xff));
    h.push_back(static_cast<char>(n & 0xff));
  } else {
    h.push_back(127);
    for (int i = 7; i >= 0; --i) h.push_back(static_cast<char>((n >> (i * 8)) & 0xff));
  }
  h.append(static_cast<const char*>(payload), n);
  return h;
}

bool send_all(int fd, const void* p, std::size_t n) {
  const auto* b = static_cast<const std::uint8_t*>(p);
  std::size_t off = 0;
  while (off < n) {
    ssize_t w = ::send(fd, b + off, n - off, MSG_NOSIGNAL);
    if (w < 0) {
      if (errno == EINTR) continue;
      if (errno == EAGAIN || errno == EWOULDBLOCK) continue;
      return false;
    }
    if (w == 0) return false;
    off += static_cast<std::size_t>(w);
  }
  return true;
}

bool recv_exact(int fd, void* p, std::size_t n) {
  auto* b = static_cast<std::uint8_t*>(p);
  std::size_t off = 0;
  while (off < n) {
    ssize_t r = ::recv(fd, b + off, n - off, 0);
    if (r < 0) {
      if (errno == EINTR) continue;
      if (errno == EAGAIN || errno == EWOULDBLOCK) return false;
      return false;
    }
    if (r == 0) return false;
    off += static_cast<std::size_t>(r);
  }
  return true;
}

bool recv_frame(int fd, int* opcode, std::string* payload) {
  std::uint8_t hdr[2];
  if (!recv_exact(fd, hdr, 2)) return false;
  *opcode = hdr[0] & 0x0f;
  bool masked = (hdr[1] & 0x80) != 0;
  std::uint64_t length = hdr[1] & 0x7f;
  if (length == 126) {
    std::uint8_t ext[2];
    if (!recv_exact(fd, ext, 2)) return false;
    length = (static_cast<std::uint64_t>(ext[0]) << 8) | ext[1];
  } else if (length == 127) {
    std::uint8_t ext[8];
    if (!recv_exact(fd, ext, 8)) return false;
    length = 0;
    for (int i = 0; i < 8; ++i) length = (length << 8) | ext[i];
  }
  std::uint8_t mask[4]{};
  if (masked && !recv_exact(fd, mask, 4)) return false;
  payload->assign(static_cast<std::size_t>(length), '\0');
  if (length && !recv_exact(fd, payload->data(), static_cast<std::size_t>(length))) return false;
  if (masked) {
    for (std::size_t i = 0; i < payload->size(); ++i) {
      (*payload)[i] = static_cast<char>(static_cast<std::uint8_t>((*payload)[i]) ^ mask[i % 4]);
    }
  }
  return true;
}

int parse_int_at(const std::string& s, std::size_t colon) {
  std::size_t i = colon + 1;
  while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) ++i;
  int v = 0;
  bool any = false;
  while (i < s.size() && s[i] >= '0' && s[i] <= '9') {
    v = v * 10 + (s[i] - '0');
    ++i;
    any = true;
  }
  return any ? v : -1;
}

constexpr const char* kJsonSchema = R"({"type":"object","additionalProperties":true})";
constexpr const char* kImgSchema =
    R"({"type":"object","properties":{"timestamp":{"type":"object","properties":{"sec":{"type":"integer"},"nsec":{"type":"integer"}}},"frame_id":{"type":"string"},"data":{"type":"string","contentEncoding":"base64"},"format":{"type":"string"}}})";

// Foxglove advertise.schema is a JSON string (jsonschema text), not a nested object.
// Nested object → Studio JSON.parse(String(obj)) → "[object Object] is not valid JSON".
std::string json_quote(const char* s) {
  std::string o;
  o.push_back('"');
  for (const char* p = s; *p; ++p) {
    if (*p == '"' || *p == '\\') o.push_back('\\');
    o.push_back(*p);
  }
  o.push_back('"');
  return o;
}

}  // namespace

std::string channel_desc_json(int id, const std::string& topic) {
  const bool img = is_image_topic(topic);
  const std::string schema = json_quote(img ? kImgSchema : kJsonSchema);
  char buf[4096];
  std::snprintf(buf, sizeof(buf),
                "{\"id\":%d,\"topic\":\"%s\",\"encoding\":\"json\",\"schemaName\":\"%s\","
                "\"schema\":%s,\"schemaEncoding\":\"jsonschema\"}",
                id, topic.c_str(), img ? "foxglove.CompressedImage" : "gf.JsonMsg",
                schema.c_str());
  return buf;
}

namespace {

void set_nonblock(int fd) {
  int fl = fcntl(fd, F_GETFL, 0);
  if (fl >= 0) fcntl(fd, F_SETFL, fl | O_NONBLOCK);
}

}  // namespace

bool is_image_topic(const std::string& topic) {
  std::string t = topic;
  for (char& c : t) {
    if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
  }
  if (t.find("camera") != std::string::npos && t.find("compressed") != std::string::npos) {
    return true;
  }
  return t.size() >= 11 && (t.rfind("/compressed") == t.size() - 11 ||
                            t.rfind("/image") == t.size() - 6);
}

std::string compressed_image_json(std::uint64_t t_ns, const std::string& png,
                                  const char* frame_id) {
  const std::uint64_t sec = t_ns / 1000000000ull;
  const std::uint64_t nsec = t_ns % 1000000000ull;
  std::string b64 = b64_encode(png.data(), png.size());
  std::string o;
  o.reserve(b64.size() + 160);
  char head[192];
  std::snprintf(head, sizeof(head),
                "{\"timestamp\":{\"sec\":%llu,\"nsec\":%llu},\"frame_id\":\"%s\","
                "\"format\":\"png\",\"data\":\"",
                static_cast<unsigned long long>(sec), static_cast<unsigned long long>(nsec),
                frame_id ? frame_id : "front");
  o = head;
  o += b64;
  o += "\"}";
  return o;
}

struct WsHub::Client {
  int fd = -1;
  std::map<std::string, int> topic_to_channel;
  std::map<int, int> subscriptions;          // sub_id → channel_id
  std::map<int, std::vector<int>> channel_subs;  // channel_id → sub_ids
  int next_channel = 1;

  int ensure_channel(const std::string& topic) {
    auto it = topic_to_channel.find(topic);
    if (it != topic_to_channel.end()) return it->second;
    int cid = next_channel++;
    topic_to_channel[topic] = cid;
    std::string payload = std::string("{\"op\":\"advertise\",\"channels\":[") +
                          channel_desc_json(cid, topic) + "]}";
    auto fr = ws_frame(0x1, payload.data(), payload.size());
    send_all(fd, fr.data(), fr.size());
    return cid;
  }
};

WsHub::WsHub() = default;

WsHub::~WsHub() {
  for (auto* c : clients_) {
    if (c->fd >= 0) ::close(c->fd);
    delete c;
  }
  if (listen_fd_ >= 0) ::close(listen_fd_);
}

void WsHub::set_name(std::string name) { name_ = std::move(name); }

bool WsHub::listen(const std::string& host, std::uint16_t port) {
  listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (listen_fd_ < 0) return false;
  int yes = 1;
  setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  if (host.empty() || host == "0.0.0.0") {
    addr.sin_addr.s_addr = INADDR_ANY;
  } else if (inet_pton(AF_INET, host.c_str(), &addr.sin_addr) != 1) {
    addr.sin_addr.s_addr = INADDR_ANY;
  }
  if (bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
    std::cerr << "gf-foxglove-ws: bind failed port=" << port << " errno=" << errno << "\n";
    ::close(listen_fd_);
    listen_fd_ = -1;
    return false;
  }
  if (::listen(listen_fd_, 8) < 0) {
    ::close(listen_fd_);
    listen_fd_ = -1;
    return false;
  }
  set_nonblock(listen_fd_);
  char ip[64];
  inet_ntop(AF_INET, &addr.sin_addr, ip, sizeof(ip));
  bind_desc_ = std::string("ws://") + ip + ":" + std::to_string(port);
  std::cerr << "gf-foxglove-ws: listen " << bind_desc_ << "\n";
  return true;
}

void WsHub::advertise(const std::vector<std::string>& topics) { topics_ = topics; }

bool WsHub::handshake(int fd) {
  std::string req;
  char tmp[1024];
  while (req.find("\r\n\r\n") == std::string::npos) {
    ssize_t r = ::recv(fd, tmp, sizeof(tmp), 0);
    if (r <= 0) return false;
    req.append(tmp, static_cast<std::size_t>(r));
    if (req.size() > 8192) return false;
  }
  std::string key;
  std::string lower = req;
  for (char& c : lower) {
    if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
  }
  auto pos = lower.find("sec-websocket-key:");
  if (pos == std::string::npos) return false;
  pos = req.find(':', pos);
  auto end = req.find("\r\n", pos);
  key = req.substr(pos + 1, end - pos - 1);
  while (!key.empty() && (key.front() == ' ' || key.front() == '\t')) key.erase(key.begin());
  while (!key.empty() && (key.back() == ' ' || key.back() == '\t' || key.back() == '\r')) {
    key.pop_back();
  }
  if (key.empty()) return false;
  std::string accept = ws_accept_key(key);
  // Studio requires a foxglove.* subprotocol in the 101; omit → "not reachable".
  std::string proto = "foxglove.websocket.v1";
  auto ppos = lower.find("sec-websocket-protocol:");
  if (ppos != std::string::npos) {
    auto pend = req.find("\r\n", ppos);
    std::string offered = lower.substr(ppos, pend == std::string::npos ? std::string::npos : pend - ppos);
    if (offered.find("foxglove.websocket.v2") != std::string::npos) proto = "foxglove.websocket.v2";
    if (offered.find("foxglove.websocket.v1") != std::string::npos) proto = "foxglove.websocket.v1";
  }
  std::string resp =
      "HTTP/1.1 101 Switching Protocols\r\n"
      "Upgrade: websocket\r\n"
      "Connection: Upgrade\r\n"
      "Sec-WebSocket-Accept: " +
      accept +
      "\r\n"
      "Sec-WebSocket-Protocol: " +
      proto + "\r\n\r\n";
  return send_all(fd, resp.data(), resp.size());
}

void WsHub::accept_one() {
  sockaddr_in peer{};
  socklen_t sl = sizeof(peer);
  int fd = ::accept(listen_fd_, reinterpret_cast<sockaddr*>(&peer), &sl);
  if (fd < 0) return;
  int yes = 1;
  setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
  // Handshake is short; temporarily blocking.
  if (!handshake(fd)) {
    ::close(fd);
    return;
  }
  auto* c = new Client;
  c->fd = fd;
  std::string info = std::string("{\"op\":\"serverInfo\",\"name\":\"") + name_ +
                     "\",\"capabilities\":[],\"supportedEncodings\":[\"json\"]}";
  auto fr = ws_frame(0x1, info.data(), info.size());
  if (!send_all(fd, fr.data(), fr.size())) {
    ::close(fd);
    delete c;
    return;
  }
  if (!topics_.empty()) {
    std::string chs = "{\"op\":\"advertise\",\"channels\":[";
    for (std::size_t i = 0; i < topics_.size(); ++i) {
      int cid = c->next_channel++;
      c->topic_to_channel[topics_[i]] = cid;
      if (i) chs += ",";
      chs += channel_desc_json(cid, topics_[i]);
    }
    chs += "]}";
    auto afr = ws_frame(0x1, chs.data(), chs.size());
    send_all(fd, afr.data(), afr.size());
  }
  clients_.push_back(c);
  std::cerr << "gf-foxglove-ws: client connected n=" << clients_.size() << "\n";
}

void WsHub::drop_client(std::size_t i) {
  auto* c = clients_[i];
  if (c->fd >= 0) ::close(c->fd);
  delete c;
  clients_.erase(clients_.begin() + static_cast<std::ptrdiff_t>(i));
  std::cerr << "gf-foxglove-ws: client gone n=" << clients_.size() << "\n";
}

void WsHub::poll() {
  if (listen_fd_ < 0) return;
  fd_set rfds;
  FD_ZERO(&rfds);
  FD_SET(listen_fd_, &rfds);
  int maxfd = listen_fd_;
  for (auto* c : clients_) {
    if (c->fd < 0) continue;
    FD_SET(c->fd, &rfds);
    if (c->fd > maxfd) maxfd = c->fd;
  }
  timeval tv{0, 0};
  int nsel = ::select(maxfd + 1, &rfds, nullptr, nullptr, &tv);
  if (nsel < 0) return;
  if (FD_ISSET(listen_fd_, &rfds)) accept_one();
  for (std::size_t i = 0; i < clients_.size();) {
    auto* c = clients_[i];
    if (c->fd < 0 || !FD_ISSET(c->fd, &rfds)) {
      ++i;
      continue;
    }
    bool alive = true;
    int opcode = 0;
    std::string payload;
    if (!recv_frame(c->fd, &opcode, &payload)) {
      alive = false;
    } else if (opcode == 0x8) {
      alive = false;
    } else if (opcode == 0x9) {
      auto pong = ws_frame(0xA, payload.data(), payload.size());
      send_all(c->fd, pong.data(), pong.size());
    } else if (opcode == 0x1) {
      if (payload.find("\"subscribe\"") != std::string::npos) {
        std::size_t pos = 0;
        while (true) {
          auto p = payload.find("\"channelId\"", pos);
          if (p == std::string::npos) break;
          auto colon = payload.find(':', p);
          int cid = parse_int_at(payload, colon);
          auto obj = payload.rfind('{', p);
          int sid = -1;
          if (obj != std::string::npos) {
            auto idp = payload.find("\"id\"", obj);
            if (idp != std::string::npos && idp < p + 40) {
              sid = parse_int_at(payload, payload.find(':', idp));
            }
          }
          if (sid >= 0 && cid >= 0) {
            c->subscriptions[sid] = cid;
            auto& lst = c->channel_subs[cid];
            if (std::find(lst.begin(), lst.end(), sid) == lst.end()) lst.push_back(sid);
            std::string topic = "?";
            for (const auto& kv : c->topic_to_channel) {
              if (kv.second == cid) topic = kv.first;
            }
            std::cerr << "gf-foxglove-ws: subscribe sub=" << sid << " channel=" << cid
                      << " topic=" << topic << "\n";
          }
          pos = p + 1;
        }
      } else if (payload.find("\"unsubscribe\"") != std::string::npos) {
        std::size_t pos = 0;
        while (true) {
          auto p = payload.find_first_of("0123456789", pos);
          if (p == std::string::npos) break;
          if (payload.find("subscriptionIds", 0) != std::string::npos &&
              p > payload.find("subscriptionIds")) {
            int sid = 0;
            while (p < payload.size() && payload[p] >= '0' && payload[p] <= '9') {
              sid = sid * 10 + (payload[p] - '0');
              ++p;
            }
            auto it = c->subscriptions.find(sid);
            if (it != c->subscriptions.end()) {
              int cid = it->second;
              c->subscriptions.erase(it);
              auto& lst = c->channel_subs[cid];
              lst.erase(std::remove(lst.begin(), lst.end(), sid), lst.end());
            }
            pos = p;
          } else {
            pos = p + 1;
          }
        }
      }
    }
    if (!alive) {
      drop_client(i);
    } else {
      ++i;
    }
  }
}

int WsHub::publish_json(const std::string& topic, std::uint64_t t_ns, std::string_view json) {
  int sent = 0;
  for (auto* c : clients_) {
    int cid = c->ensure_channel(topic);
    auto it = c->channel_subs.find(cid);
    if (it == c->channel_subs.end() || it->second.empty()) continue;
    for (int sid : it->second) {
      std::string bin;
      bin.resize(1 + 4 + 8 + json.size());
      bin[0] = 0x01;
      std::uint32_t s32 = static_cast<std::uint32_t>(sid);
      std::memcpy(&bin[1], &s32, 4);
      std::memcpy(&bin[5], &t_ns, 8);
      std::memcpy(&bin[13], json.data(), json.size());
      auto fr = ws_frame(0x2, bin.data(), bin.size());
      if (send_all(c->fd, fr.data(), fr.size())) ++sent;
    }
  }
  return sent;
}

bool WsHub::has_client() const { return !clients_.empty(); }
int WsHub::client_count() const { return static_cast<int>(clients_.size()); }

}  // namespace gf_foxglove
