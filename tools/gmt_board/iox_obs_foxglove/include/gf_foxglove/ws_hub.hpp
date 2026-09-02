#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace gf_foxglove {

// Foxglove WebSocket subset: serverInfo, advertise, subscribe, binary opcode 0x01.
class WsHub {
 public:
  WsHub();
  ~WsHub();

  WsHub(const WsHub&) = delete;
  WsHub& operator=(const WsHub&) = delete;

  bool listen(const std::string& host, std::uint16_t port);
  void set_name(std::string name);

  // Advertise topics up front so Studio can subscribe before the first sample.
  void advertise(const std::vector<std::string>& topics);

  // Accept + client control frames (subscribe / ping / close).
  void poll();

  // JSON payload is the Foxglove channel data object (not the tap NDJSON wrapper).
  int publish_json(const std::string& topic, std::uint64_t t_ns, std::string_view json);

  bool has_client() const;
  int client_count() const;
  const std::string& bind_desc() const { return bind_desc_; }

 private:
  struct Client;
  int listen_fd_ = -1;
  std::string name_ = "gf_foxglove_ws";
  std::string bind_desc_;
  std::vector<std::string> topics_;
  std::vector<Client*> clients_;

  void accept_one();
  void drop_client(std::size_t i);
  static bool handshake(int fd);
};

std::string compressed_image_json(std::uint64_t t_ns, const std::string& png,
                                  const char* frame_id);

bool is_image_topic(const std::string& topic);

// Advertise channel JSON. schema is a quoted jsonschema string (Foxglove WS spec).
std::string channel_desc_json(int id, const std::string& topic);

}  // namespace gf_foxglove
