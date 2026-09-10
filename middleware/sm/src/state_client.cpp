#include "gf_ara/sm/state_client.hpp"

#include <gf_ara/log/logger.hpp>

#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>

#if defined(__linux__) || defined(__APPLE__)
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#endif

namespace gf_ara::sm {
namespace {

std::mutex& Mutex() {
  static std::mutex m;
  return m;
}

bool Allowed(FunctionGroupState from, FunctionGroupState to) noexcept {
  if (from == to) {
    return true;
  }
  switch (from) {
    case FunctionGroupState::kOff:
      return to == FunctionGroupState::kRunning;
    case FunctionGroupState::kRunning:
      return to == FunctionGroupState::kUpdating || to == FunctionGroupState::kOff;
    case FunctionGroupState::kUpdating:
      return to == FunctionGroupState::kRunning || to == FunctionGroupState::kOff;
  }
  return false;
}

bool AllowedNamed(std::string_view /*fg*/, std::string_view from, std::string_view to) {
  if (from == to) {
    return true;
  }
  // ModeDeclaration: any non-empty target (OEM declares legal set in exec.yaml).
  return !to.empty();
}

#if defined(__linux__) || defined(__APPLE__)
constexpr const char kFgStoreShmName[] = "/gf_ara_fg_state";
constexpr std::size_t kFgIdBytes = 64;
constexpr std::size_t kFgStateBytes = 64;
constexpr std::size_t kFgStoreSlots = 16;

struct FgStoreSlot {
  char fg_id[kFgIdBytes];
  char state[kFgStateBytes];
};

struct FgStoreLayout {
  std::uint32_t magic;
  std::uint32_t version;
  FgStoreSlot slots[kFgStoreSlots];
};

constexpr std::uint32_t kFgStoreMagic = 0x47464647u;  // 'GFFG'
constexpr std::uint32_t kFgStoreVersion = 1;

FgStoreLayout* MapFgStore(bool create) {
  const int oflag = create ? (O_CREAT | O_RDWR) : O_RDWR;
  const int fd = ::shm_open(kFgStoreShmName, oflag, 0600);
  if (fd < 0) {
    return nullptr;
  }
  if (create) {
    if (::ftruncate(fd, static_cast<off_t>(sizeof(FgStoreLayout))) != 0) {
      ::close(fd);
      return nullptr;
    }
  }
  void* p = ::mmap(nullptr, sizeof(FgStoreLayout), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  ::close(fd);
  if (p == MAP_FAILED) {
    return nullptr;
  }
  auto* layout = static_cast<FgStoreLayout*>(p);
  if (create && layout->magic != kFgStoreMagic) {
    std::memset(layout, 0, sizeof(*layout));
    layout->magic = kFgStoreMagic;
    layout->version = kFgStoreVersion;
  }
  if (layout->magic != kFgStoreMagic) {
    ::munmap(layout, sizeof(FgStoreLayout));
    return nullptr;
  }
  return layout;
}

void UnmapFgStore(FgStoreLayout* layout) {
  if (layout != nullptr) {
    ::munmap(layout, sizeof(FgStoreLayout));
  }
}
#endif

}  // namespace

const char* ToString(FunctionGroupState s) noexcept {
  switch (s) {
    case FunctionGroupState::kOff:
      return "Off";
    case FunctionGroupState::kRunning:
      return "Running";
    case FunctionGroupState::kUpdating:
      return "Updating";
  }
  return "?";
}

std::unordered_map<std::string, StateClient::Entry>& StateClient::Table() {
  static std::unordered_map<std::string, Entry> t;
  return t;
}

bool StateClient::PublishFgState(std::string_view fg_id, std::string_view state_name) {
  if (fg_id.empty() || state_name.empty()) {
    return false;
  }
#if defined(__linux__) || defined(__APPLE__)
  FgStoreLayout* layout = MapFgStore(true);
  if (layout == nullptr) {
    gf_ara::log::Logger::Instance().Error("sm", "sm: cannot map FgStateStore shm");
    return false;
  }
  const std::string id(fg_id);
  const std::string st(state_name);
  int free_slot = -1;
  for (std::size_t i = 0; i < kFgStoreSlots; ++i) {
    if (layout->slots[i].fg_id[0] == '\0') {
      if (free_slot < 0) {
        free_slot = static_cast<int>(i);
      }
      continue;
    }
    if (id == layout->slots[i].fg_id) {
      std::snprintf(layout->slots[i].state, kFgStateBytes, "%s", st.c_str());
      UnmapFgStore(layout);
      return true;
    }
  }
  if (free_slot < 0) {
    UnmapFgStore(layout);
    gf_ara::log::Logger::Instance().Error("sm", "sm: FgStateStore full");
    return false;
  }
  std::snprintf(layout->slots[free_slot].fg_id, kFgIdBytes, "%s", id.c_str());
  std::snprintf(layout->slots[free_slot].state, kFgStateBytes, "%s", st.c_str());
  UnmapFgStore(layout);
  return true;
#else
  (void)fg_id;
  (void)state_name;
  return false;
#endif
}

std::string StateClient::ReadFgState(std::string_view fg_id) {
  if (fg_id.empty()) {
    return {};
  }
#if defined(__linux__) || defined(__APPLE__)
  FgStoreLayout* layout = MapFgStore(false);
  if (layout == nullptr) {
    return {};
  }
  const std::string id(fg_id);
  std::string out;
  for (std::size_t i = 0; i < kFgStoreSlots; ++i) {
    if (layout->slots[i].fg_id[0] == '\0') {
      continue;
    }
    if (id == layout->slots[i].fg_id) {
      out = layout->slots[i].state;
      break;
    }
  }
  UnmapFgStore(layout);
  return out;
#else
  (void)fg_id;
  return {};
#endif
}

void StateClient::EnsureGroup(std::string_view fg_id, FunctionGroupState initial) {
  if (fg_id.empty()) {
    return;
  }
  std::lock_guard lock(Mutex());
  auto& table = Table();
  const auto key = std::string(fg_id);
  const auto [it, inserted] = table.try_emplace(key);
  if (inserted) {
    it->second.state = initial;
    it->second.use_named = false;
    gf_ara::log::Logger::Instance().Info(
        "sm", std::string("sm: ensure fg=") + key + " initial=" + ToString(initial));
  }
}

void StateClient::EnsureGroupNamed(std::string_view fg_id, std::string_view initial) {
  if (fg_id.empty() || initial.empty()) {
    return;
  }
  std::lock_guard lock(Mutex());
  auto& table = Table();
  const auto key = std::string(fg_id);
  const auto [it, inserted] = table.try_emplace(key);
  if (inserted) {
    it->second.use_named = true;
    it->second.named_state = std::string(initial);
    gf_ara::log::Logger::Instance().Info(
        "sm", std::string("sm: ensure fg=") + key + " initial=" + std::string(initial));
  }
}

FunctionGroupState StateClient::GetState(std::string_view fg_id) noexcept {
  std::lock_guard lock(Mutex());
  const auto it = Table().find(std::string(fg_id));
  if (it == Table().end() || it->second.use_named) {
    return FunctionGroupState::kOff;
  }
  return it->second.state;
}

std::string StateClient::GetStateNamed(std::string_view fg_id) {
  std::lock_guard lock(Mutex());
  const auto it = Table().find(std::string(fg_id));
  if (it == Table().end() || !it->second.use_named) {
    return {};
  }
  return it->second.named_state;
}

bool StateClient::RequestTransition(std::string_view fg_id, FunctionGroupState target) {
  if (fg_id.empty()) {
    return false;
  }
  std::lock_guard lock(Mutex());
  auto& e = Table()[std::string(fg_id)];
  if (e.use_named) {
    gf_ara::log::Logger::Instance().Error(
        "sm", std::string("sm: classic transition on named fg=") + std::string(fg_id));
    return false;
  }
  if (!Allowed(e.state, target)) {
    gf_ara::log::Logger::Instance().Error(
        "sm", std::string("sm: illegal transition fg=") + std::string(fg_id) + " " +
                 ToString(e.state) + "→" + ToString(target));
    return false;
  }
  if (e.state != target) {
    gf_ara::log::Logger::Instance().Info(
        "sm", std::string("sm: transition fg=") + std::string(fg_id) + " " +
                 ToString(e.state) + "→" + ToString(target));
    e.state = target;
  }
  return true;
}

bool StateClient::RequestTransitionNamed(std::string_view fg_id, std::string_view target) {
  if (fg_id.empty() || target.empty()) {
    return false;
  }
  std::string from;
  {
    std::lock_guard lock(Mutex());
    auto& e = Table()[std::string(fg_id)];
    if (!e.use_named) {
      e.use_named = true;
      e.named_state.clear();
    }
    from = e.named_state;
    if (!AllowedNamed(fg_id, from, target)) {
      gf_ara::log::Logger::Instance().Error(
          "sm", std::string("sm: illegal named transition fg=") + std::string(fg_id) +
                   " " + (from.empty() ? "(none)" : from) + "→" + std::string(target));
      return false;
    }
    if (from != target) {
      gf_ara::log::Logger::Instance().Info(
          "sm", std::string("sm: transition fg=") + std::string(fg_id) + " " +
                   (from.empty() ? "(none)" : from) + "→" + std::string(target));
      e.named_state = std::string(target);
    }
  }
  (void)PublishFgState(fg_id, target);
  return true;
}

void StateClient::NotifyHealthFault(std::string_view fg_id, std::string_view entity,
                                    std::string_view reason, bool enter_updating) {
  if (fg_id.empty()) {
    fg_id = "MachineFG";
  }
  {
    std::lock_guard lock(Mutex());
    auto& e = Table()[std::string(fg_id)];
    ++e.faults;
    gf_ara::log::Logger::Instance().Info(
        "sm", std::string("sm: health_fault fg=") + std::string(fg_id) +
                 " entity=" + std::string(entity) + " reason=" + std::string(reason) +
                 " faults=" + std::to_string(e.faults));
  }
  if (enter_updating) {
    RequestTransition(fg_id, FunctionGroupState::kUpdating);
  }
}

std::uint32_t StateClient::FaultCount(std::string_view fg_id) noexcept {
  std::lock_guard lock(Mutex());
  const auto it = Table().find(std::string(fg_id));
  if (it == Table().end()) {
    return 0;
  }
  return it->second.faults;
}

}  // namespace gf_ara::sm
