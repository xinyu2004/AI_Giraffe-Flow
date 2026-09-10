#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <unordered_map>

namespace gf_ara::sm {

/// MachineFG / OTA — classic three states.
enum class FunctionGroupState : std::uint8_t {
  kOff = 0,
  kRunning,
  kUpdating,
};

[[nodiscard]] const char* ToString(FunctionGroupState s) noexcept;

/// In-process Function Group table (SIL) + cross-process FgStateStore (POSIX shm).
/// ModeDeclaration FGs use arbitrary state name strings; product names (DrivingActive,
/// EmbActive, …) live in Apps, not in this middleware.
class StateClient {
 public:
  static void EnsureGroup(std::string_view fg_id, FunctionGroupState initial);
  [[nodiscard]] static FunctionGroupState GetState(std::string_view fg_id) noexcept;
  static bool RequestTransition(std::string_view fg_id, FunctionGroupState target);

  /// Named ModeDeclaration states (any non-empty string).
  static void EnsureGroupNamed(std::string_view fg_id, std::string_view initial);
  [[nodiscard]] static std::string GetStateNamed(std::string_view fg_id);
  static bool RequestTransitionNamed(std::string_view fg_id, std::string_view target);

  /// Cross-process FG state (EM set-difference). Keyed by fg_id.
  static bool PublishFgState(std::string_view fg_id, std::string_view state_name);
  [[nodiscard]] static std::string ReadFgState(std::string_view fg_id);

  static void NotifyHealthFault(std::string_view fg_id, std::string_view entity,
                                std::string_view reason, bool enter_updating = false);
  [[nodiscard]] static std::uint32_t FaultCount(std::string_view fg_id) noexcept;

 private:
  struct Entry {
    FunctionGroupState state{FunctionGroupState::kOff};
    std::string named_state;
    bool use_named{false};
    std::uint32_t faults{0};
  };
  static std::unordered_map<std::string, Entry>& Table();
};

}  // namespace gf_ara::sm
