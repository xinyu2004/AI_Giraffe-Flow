#ifndef GF_ARA_PER_KEY_VALUE_STORAGE_HPP
#define GF_ARA_PER_KEY_VALUE_STORAGE_HPP

#include <gf_ara/core/result.hpp>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace gf_ara::per {

/// In-process KV stub (ara::per subset). Not SQLite yet — SKU-trimmable skeleton.
class KeyValueStorage {
 public:
  static KeyValueStorage& Instance();

  gf_ara::core::Result<void> Open(std::string_view instance);
  [[nodiscard]] bool IsOpen() const noexcept;

  gf_ara::core::Result<void> SetValue(std::string_view key, std::string_view value);
  gf_ara::core::Result<std::string> GetValue(std::string_view key) const;
  void Clear();

  [[nodiscard]] const std::string& InstanceName() const noexcept { return instance_; }

 private:
  KeyValueStorage() = default;
  std::string instance_;
  bool open_{false};
  mutable std::mutex mu_;
  std::unordered_map<std::string, std::string> store_;
};

}  // namespace gf_ara::per

#endif
