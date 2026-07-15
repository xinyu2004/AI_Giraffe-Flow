#include "gf_ara/com/binding/someip/runtime.hpp"

#include <mutex>
#include <string>

namespace gf_ara::com::binding::someip {
namespace {

std::mutex g_mu;
bool g_init{false};
std::string g_name;

}  // namespace

void InitRuntime(const std::string& app_name) {
  std::lock_guard<std::mutex> lock(g_mu);
  g_name = app_name;
  g_init = true;
}

void Shutdown() noexcept {
  std::lock_guard<std::mutex> lock(g_mu);
  g_init = false;
  g_name.clear();
}

bool IsInitialized() noexcept {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_init;
}

std::string_view BackendName() noexcept {
#if defined(GF_SOMEIP_USE_VSOMEIP) && GF_SOMEIP_USE_VSOMEIP
  return "vsomeip";
#else
  return "stub";
#endif
}

}  // namespace gf_ara::com::binding::someip
