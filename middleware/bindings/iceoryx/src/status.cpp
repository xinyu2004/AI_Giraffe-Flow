#include "gf_ara/com/binding/iceoryx/status.hpp"

// Touch iceoryx headers so the binding target fails fast if the pin is wrong.
#include "iceoryx_posh/runtime/posh_runtime.hpp"

namespace gf_ara::com::binding::iceoryx {

bool BackendLinked() noexcept { return true; }

}  // namespace gf_ara::com::binding::iceoryx
