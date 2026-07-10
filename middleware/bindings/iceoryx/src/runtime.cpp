#include "gf_ara/com/binding/iceoryx/runtime.hpp"

#include "iceoryx_hoofs/cxx/string.hpp"
#include "iceoryx_posh/runtime/posh_runtime.hpp"

namespace gf_ara::com::binding::iceoryx {

void InitRuntime(const std::string& app_name) {
  using RuntimeName_t = iox::RuntimeName_t;
  RuntimeName_t name(iox::cxx::TruncateToCapacity, app_name.c_str());
  iox::runtime::PoshRuntime::initRuntime(name);
}

}  // namespace gf_ara::com::binding::iceoryx
