#include "gf_ara/com/binding/dds/runtime.hpp"

#include <mutex>
#include <string>

namespace gf_ara::com::binding::dds {
namespace {

std::mutex g_mu;
bool g_init{false};
std::string g_name;

}  // namespace

void InitRuntime(const std::string& participant_name) {
  std::lock_guard<std::mutex> lock(g_mu);
  g_name = participant_name;
  g_init = true;
}

std::string_view BackendName() noexcept {
#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS
  return "cyclonedds";
#else
  return "stub";
#endif
}

bool IsInitialized() noexcept {
  std::lock_guard<std::mutex> lock(g_mu);
  return g_init;
}

}  // namespace gf_ara::com::binding::dds
