#pragma once

#include <string>
#include <string_view>

namespace gf_ara::com::binding::someip {

/// P1 stub: vsomeip integration is staged — Initialize/Shutdown only.
void InitRuntime(const std::string& app_name);
void Shutdown() noexcept;
[[nodiscard]] bool IsInitialized() noexcept;
[[nodiscard]] std::string_view BackendName() noexcept;  // "stub" | "vsomeip"

}  // namespace gf_ara::com::binding::someip
