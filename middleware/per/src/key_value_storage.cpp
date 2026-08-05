#include "gf_ara/per/key_value_storage.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <sys/stat.h>
#include <unistd.h>

namespace gf_ara::per {
namespace {

std::string Escape(std::string_view s) {
  std::string o;
  o.reserve(s.size());
  for (char c : s) {
    if (c == '\\') {
      o += "\\\\";
    } else if (c == '\n') {
      o += "\\n";
    } else if (c == '=') {
      o += "\\=";
    } else {
      o.push_back(c);
    }
  }
  return o;
}

std::string Unescape(std::string_view s) {
  std::string o;
  o.reserve(s.size());
  for (std::size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '\\' && i + 1 < s.size()) {
      const char n = s[++i];
      if (n == 'n') {
        o.push_back('\n');
      } else {
        o.push_back(n);
      }
    } else {
      o.push_back(s[i]);
    }
  }
  return o;
}

bool ParseFile(const std::string& path, std::uint64_t& gen_out,
               std::unordered_map<std::string, std::string>& store_out) {
  std::ifstream in(path);
  if (!in) {
    return false;
  }
  std::string line;
  if (!std::getline(in, line)) {
    return false;
  }
  const std::string kPrefix = "#gen=";
  if (line.compare(0, kPrefix.size(), kPrefix) != 0) {
    return false;
  }
  try {
    gen_out = static_cast<std::uint64_t>(std::stoull(line.substr(kPrefix.size())));
  } catch (...) {
    return false;
  }
  store_out.clear();
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const auto eq = line.find('=');
    if (eq == std::string::npos) {
      continue;
    }
    store_out[Unescape(line.substr(0, eq))] = Unescape(line.substr(eq + 1));
  }
  return true;
}

bool WriteAtomic(const std::string& path, std::uint64_t gen,
                 const std::unordered_map<std::string, std::string>& store) {
  const std::string tmp = path + ".tmp";
  {
    std::ofstream out(tmp, std::ios::trunc);
    if (!out) {
      return false;
    }
    out << "#gen=" << gen << '\n';
    for (const auto& kv : store) {
      out << Escape(kv.first) << '=' << Escape(kv.second) << '\n';
    }
    out.flush();
    if (!out) {
      return false;
    }
  }
  if (::rename(tmp.c_str(), path.c_str()) != 0) {
    ::unlink(tmp.c_str());
    return false;
  }
  return true;
}

}  // namespace

KeyValueStorage& KeyValueStorage::Instance() {
  static KeyValueStorage inst;
  return inst;
}

std::string KeyValueStorage::DirPath() const {
  const char* d = std::getenv("GF_PER_DIR");
  if (d == nullptr || d[0] == '\0') {
    return ".";
  }
  return std::string(d);
}

std::string KeyValueStorage::SlotPath(char slot) const {
  return DirPath() + "/" + instance_ + ".kv." + slot;
}

bool KeyValueStorage::LoadBestSlotLocked() {
  std::uint64_t ga = 0;
  std::uint64_t gb = 0;
  std::unordered_map<std::string, std::string> sa;
  std::unordered_map<std::string, std::string> sb;
  const bool ok_a = ParseFile(SlotPath('a'), ga, sa);
  const bool ok_b = ParseFile(SlotPath('b'), gb, sb);
  if (!ok_a && !ok_b) {
    generation_ = 0;
    active_slot_ = 'a';
    store_.clear();
    return true;
  }
  if (ok_a && (!ok_b || ga >= gb)) {
    generation_ = ga;
    active_slot_ = 'a';
    store_ = std::move(sa);
  } else {
    generation_ = gb;
    active_slot_ = 'b';
    store_ = std::move(sb);
  }
  return true;
}

bool KeyValueStorage::PersistLocked() {
  const char next = (active_slot_ == 'a') ? 'b' : 'a';
  const std::uint64_t gen = generation_ + 1;
  if (!WriteAtomic(SlotPath(next), gen, store_)) {
    return false;
  }
  generation_ = gen;
  active_slot_ = next;
  return true;
}

gf_ara::core::Result<void> KeyValueStorage::Open(std::string_view instance) {
  std::lock_guard lock(mu_);
  if (instance.empty()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  ::mkdir(DirPath().c_str(), 0755);
  instance_ = std::string(instance);
  open_ = true;
  LoadBestSlotLocked();
  return gf_ara::core::Result<void>::Ok();
}

bool KeyValueStorage::IsOpen() const noexcept {
  std::lock_guard lock(mu_);
  return open_;
}

gf_ara::core::Result<void> KeyValueStorage::ReloadFromDisk() {
  std::lock_guard lock(mu_);
  if (!open_) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  LoadBestSlotLocked();
  return gf_ara::core::Result<void>::Ok();
}

void KeyValueStorage::ConfigureBounds(std::uint32_t max_keys, std::uint32_t max_value_bytes) {
  std::lock_guard lock(mu_);
  max_keys_ = max_keys == 0 ? 1024 : max_keys;
  max_value_bytes_ = max_value_bytes == 0 ? 65536 : max_value_bytes;
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
  if (value.size() > max_value_bytes_) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  const std::string k(key);
  if (store_.find(k) == store_.end() && store_.size() >= max_keys_) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kInvalidArgument);
  }
  store_[k] = std::string(value);
  if (!PersistLocked()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
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

gf_ara::core::Result<void> KeyValueStorage::ClearValues() {
  std::lock_guard lock(mu_);
  if (!open_) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  store_.clear();
  if (!PersistLocked()) {
    return gf_ara::core::Result<void>::Err(gf_ara::core::ErrorCode::kNotAvailable);
  }
  return gf_ara::core::Result<void>::Ok();
}

void KeyValueStorage::Close() {
  std::lock_guard lock(mu_);
  open_ = false;
  instance_.clear();
  store_.clear();
  generation_ = 0;
}

void KeyValueStorage::ResetForTest() {
  Close();
}

}  // namespace gf_ara::per
