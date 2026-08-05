#ifndef GF_ARA_PER_KEY_VALUE_STORAGE_HPP
#define GF_ARA_PER_KEY_VALUE_STORAGE_HPP

#include <gf_ara/core/result.hpp>
#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace gf_ara::per {

/// File-backed KV (gf_ara::per lite). Dual-slot under GF_PER_DIR (default: .).
/// Not SQLite. Format: `#gen=N` then `key=value` lines.
class KeyValueStorage {
 public:
  static KeyValueStorage& Instance();

  /// Open instance; loads newest valid slot from disk (if present).
  gf_ara::core::Result<void> Open(std::string_view instance);
  [[nodiscard]] bool IsOpen() const noexcept;

  /// BL-MEM-BOUND (defaults: 1024 keys, 64 KiB value).
  void ConfigureBounds(std::uint32_t max_keys, std::uint32_t max_value_bytes);

  /// Re-read newest slot from disk (cross-process writers). Instance must be open.
  gf_ara::core::Result<void> ReloadFromDisk();

  gf_ara::core::Result<void> SetValue(std::string_view key, std::string_view value);
  gf_ara::core::Result<std::string> GetValue(std::string_view key) const;
  /// Remove all keys and persist empty store (instance stays open).
  gf_ara::core::Result<void> ClearValues();
  void Close();

  [[nodiscard]] const std::string& InstanceName() const noexcept { return instance_; }

  /// Test helper: wipe in-memory + close (does not delete files).
  void ResetForTest();

 private:
  KeyValueStorage() = default;
  [[nodiscard]] std::string DirPath() const;
  [[nodiscard]] std::string SlotPath(char slot) const;
  bool LoadBestSlotLocked();
  bool PersistLocked();

  std::string instance_;
  bool open_{false};
  std::uint64_t generation_{0};
  char active_slot_{'a'};
  std::uint32_t max_keys_{1024};
  std::uint32_t max_value_bytes_{65536};
  mutable std::mutex mu_;
  std::unordered_map<std::string, std::string> store_;
};

}  // namespace gf_ara::per

#endif
