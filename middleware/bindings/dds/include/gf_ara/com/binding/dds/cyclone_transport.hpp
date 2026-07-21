#pragma once

#include "gf_ara/com/service_path.hpp"

#include <cstdint>
#include <string>

namespace gf_ara::com::binding::dds {

#if defined(GF_DDS_USE_CYCLONEDDS) && GF_DDS_USE_CYCLONEDDS

/// Opaque handle to a CycloneDDS writer (process-local).
class CycloneWriter {
 public:
  CycloneWriter() = default;
  explicit CycloneWriter(const ServicePath& path);
  CycloneWriter(const CycloneWriter&) = delete;
  CycloneWriter& operator=(const CycloneWriter&) = delete;
  CycloneWriter(CycloneWriter&& other) noexcept;
  CycloneWriter& operator=(CycloneWriter&& other) noexcept;
  ~CycloneWriter();

  [[nodiscard]] bool Ok() const noexcept { return writer_ != 0; }
  [[nodiscard]] bool Write(const void* data, std::size_t size);

 private:
  std::int32_t topic_{0};
  std::int32_t writer_{0};
};

class CycloneReader {
 public:
  CycloneReader() = default;
  explicit CycloneReader(const ServicePath& path);
  CycloneReader(const CycloneReader&) = delete;
  CycloneReader& operator=(const CycloneReader&) = delete;
  CycloneReader(CycloneReader&& other) noexcept;
  CycloneReader& operator=(CycloneReader&& other) noexcept;
  ~CycloneReader();

  [[nodiscard]] bool Ok() const noexcept { return reader_ != 0; }
  /// Returns true if a sample was copied into out (size must match published size).
  [[nodiscard]] bool Take(void* out, std::size_t size);

 private:
  std::int32_t topic_{0};
  std::int32_t reader_{0};
};

/// Ensure participant exists (called from InitRuntime).
void CycloneEnsureParticipant(const std::string& name);

#endif  // GF_DDS_USE_CYCLONEDDS

}  // namespace gf_ara::com::binding::dds
