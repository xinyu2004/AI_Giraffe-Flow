#include "gf_ara/per/key_value_storage.hpp"

namespace gf_ara::per {

KeyValueStorage& KeyValueStorage::Instance() {
  static KeyValueStorage inst;
  return inst;
}

gf_ara::core::Result<void> KeyValueStorage::Open(std::string_view instance) {
  std::lock_guard lock(mu_);
  if (instance.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  instance_ = std::string(instance);
  open_ = true;
  store_.clear();
  return gf_ara::core::Result<void>::Ok();
}

bool KeyValueStorage::IsOpen() const noexcept {
  std::lock_guard lock(mu_);
  return open_;
}

gf_ara::core::Result<void> KeyValueStorage::SetValue(std::string_view key,
                                                     std::string_view value) {
  std::lock_guard lock(mu_);
  if (!open_) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  if (key.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  store_[std::string(key)] = std::string(value);
  return gf_ara::core::Result<void>::Ok();
}

gf_ara::core::Result<std::string> KeyValueStorage::GetValue(std::string_view key) const {
  std::lock_guard lock(mu_);
  if (!open_) {
    return gf_ara::core::Result<std::string>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  const auto it = store_.find(std::string(key));
  if (it == store_.end()) {
    return gf_ara::core::Result<std::string>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  return gf_ara::core::Result<std::string>::Ok(it->second);
}

void KeyValueStorage::Clear() {
  std::lock_guard lock(mu_);
  store_.clear();
  open_ = false;
  instance_.clear();
}

}  // namespace gf_ara::per
