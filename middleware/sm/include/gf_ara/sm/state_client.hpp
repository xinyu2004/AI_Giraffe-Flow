#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <unordered_map>

namespace gf_ara::sm {

/// Minimal FG states (not a full AUTOSAR SM graph).
enum class FunctionGroupState : std::uint8_t {
  kOff = 0,
  kRunning,
  kUpdating,
};

[[nodiscard]] const char* ToString(FunctionGroupState s) noexcept;

/// In-process Function Group state machine (SIL / single address space).
/// Cross-process SM daemon is out of scope for M1.
class StateClient {
 public:
  /// Ensure FG exists; set to `initial` if first seen.
  static void EnsureGroup(std::string_view fg_id, FunctionGroupState initial);

  [[nodiscard]] static FunctionGroupState GetState(std::string_view fg_id) noexcept;

  /// Request transition. Returns false if unknown / illegal.
  static bool RequestTransition(std::string_view fg_id, FunctionGroupState target);

  /// PHM / health hook (M2): record fault; optionally enter Updating.
  /// When `enter_updating` is true, pauses supervision path via Updating state.
  static void NotifyHealthFault(std::string_view fg_id, std::string_view entity,
                                std::string_view reason, bool enter_updating = false);

  [[nodiscard]] static std::uint32_t FaultCount(std::string_view fg_id) noexcept;

 private:
  struct Entry {
    FunctionGroupState state{FunctionGroupState::kOff};
    std::uint32_t faults{0};
  };
  static std::unordered_map<std::string, Entry>& Table();
};

}  // namespace gf_ara::sm
