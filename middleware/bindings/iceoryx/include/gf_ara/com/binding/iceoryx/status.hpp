#ifndef GF_ARA_COM_BINDING_ICEORYX_STATUS_HPP
#define GF_ARA_COM_BINDING_ICEORYX_STATUS_HPP

namespace gf_ara::com::binding::iceoryx {

/// P0 skeleton: real Publisher/Subscriber over iceoryx posh lands in B3.
/// This translation unit proves the binding target links against iceoryx.
[[nodiscard]] constexpr const char* BackendName() noexcept { return "iceoryx"; }

[[nodiscard]] bool BackendLinked() noexcept;

}  // namespace gf_ara::com::binding::iceoryx

#endif
