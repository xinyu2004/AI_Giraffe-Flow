#ifndef GF_ARA_COM_BINDING_ICEORYX_RUNTIME_HPP
#define GF_ARA_COM_BINDING_ICEORYX_RUNTIME_HPP

#include <string>

namespace gf_ara::com::binding::iceoryx {

/// Must be called once per process before creating Publisher/Subscriber.
/// `app_name` must be unique among processes talking to the same RouDi.
void InitRuntime(const std::string& app_name);

}  // namespace gf_ara::com::binding::iceoryx

#endif
