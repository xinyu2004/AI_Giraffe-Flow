#ifndef GF_ARA_UCM_TRANSFER_HANDLE_HPP
#define GF_ARA_UCM_TRANSFER_HANDLE_HPP

#include <cstdint>

namespace gf_ara::ucm {

/// Transfer session handle (placeholder).
class TransferHandle {
 public:
  explicit TransferHandle(std::uint64_t id) : id_{id} {}
  [[nodiscard]] std::uint64_t Id() const { return id_; }

 private:
  std::uint64_t id_{0};
};

}  // namespace gf_ara::ucm

#endif
