#include "gf_ara/core/error_code.hpp"
#include "gf_ara/core/result.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

int Fail(const char* msg) {
  std::cerr << "gf_core_smoke FAIL: " << msg << '\n';
  return EXIT_FAILURE;
}

}  // namespace

int main() {
  using gf_ara::core::ErrorCode;
  using gf_ara::core::Result;

  {
    auto ok = Result<int>::Ok(42);
    if (!ok.HasValue() || ok.Value() != 42) {
      return Fail("Result<int>::Ok");
    }
  }

  {
    auto err = Result<int>::Err(ErrorCode::kNotAvailable);
    if (err.HasValue() || err.Error() != ErrorCode::kNotAvailable) {
      return Fail("Result<int>::Err");
    }
  }

  {
    auto ok = Result<void>::Ok();
    auto err = Result<void>::Err(ErrorCode::kBusy);
    if (!ok.HasValue() || err.HasValue() || err.Error() != ErrorCode::kBusy) {
      return Fail("Result<void>");
    }
  }

  {
    const auto name = gf_ara::core::ToString(ErrorCode::kTimeout);
    if (std::string(name) != "Timeout") {
      return Fail("ToString");
    }
  }

  std::cout << "gf_core_smoke OK\n";
  return EXIT_SUCCESS;
}
