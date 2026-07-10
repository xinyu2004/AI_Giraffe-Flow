#ifndef GF_DEMO_USS_ZONES_TOPIC_HPP
#define GF_DEMO_USS_ZONES_TOPIC_HPP

// P0 dual-process demo topic — mirrors projects/oem_a/afc_with_uss USS shape (POD).
#include <cstdint>

namespace gf::demo::uss_sensing {

struct UssZoneSample {
  uint8_t zone_id{};
  uint8_t status{};
  uint8_t distance_cm{};
};

struct UssZones {
  uint64_t timestamp_ns{};
  uint8_t sys_status{};
  uint8_t nearest_cm{};
  uint16_t zone_mask{};
  UssZoneSample zones[6]{};
};

inline constexpr const char* kService = "semantic.uss_sensing";
inline constexpr const char* kInstance = "1";
inline constexpr const char* kEvent = "UssZones";

}  // namespace gf::demo::uss_sensing

#endif
