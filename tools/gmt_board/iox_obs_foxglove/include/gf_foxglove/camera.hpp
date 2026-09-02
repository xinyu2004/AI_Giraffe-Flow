#pragma once

#include <cstdint>
#include <string>

namespace gf_foxglove {

// GfChannel shm (or file bypass) → foxglove.CompressedImage JSON. Empty if no new frame.
class CameraPub {
 public:
  explicit CameraPub(std::string slot, std::string frame_path = {});
  ~CameraPub();

  CameraPub(const CameraPub&) = delete;
  CameraPub& operator=(const CameraPub&) = delete;

  // Returns CompressedImage JSON (inner data object) or empty.
  std::string poll(std::uint64_t* t_ns_out);

  bool ok() const { return ok_; }
  const std::string& source() const { return source_; }

 private:
  void* ch_ = nullptr;
  std::string slot_;
  std::string frame_path_;
  std::string source_;
  bool ok_ = false;
  std::uint64_t last_seq_ = 0;
};

}  // namespace gf_foxglove
