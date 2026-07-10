#ifndef GF_ARA_COM_INSTANCE_ID_HPP
#define GF_ARA_COM_INSTANCE_ID_HPP

#include <cstdint>
#include <string>
#include <utility>

namespace gf_ara::com {

/// Minimal service addressing for P0 Event (not full ARA InstanceIdentifier).
struct ServicePath {
  std::string service;
  std::string instance{"1"};
  std::string event;

  [[nodiscard]] std::string Key() const {
    return service + "/" + instance + "/" + event;
  }
};

}  // namespace gf_ara::com

#endif
