#pragma once

#include <string>
#include <string_view>

namespace gf_ara::com::binding::dds {

/// Must be called once per process before Publisher/Subscriber.
void InitRuntime(const std::string& participant_name);

/// "stub" (in-process) or "cyclonedds" when linked against Eclipse CycloneDDS.
[[nodiscard]] std::string_view BackendName() noexcept;

[[nodiscard]] bool IsInitialized() noexcept;

}  // namespace gf_ara::com::binding::dds
