#include "gf_ara/core/error_code.hpp"
#include "gf_ara/core/result.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return EXIT_FAILURE;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::core::ErrorCode;
  using gf_ara::core::Result;

  {
    auto ok = Result<int>::Ok(42);
    if (!ok.HasValue() || ok.Value() != 42) {
      return Fail("CORE-01", "Result<int>::Ok");
    }
    Pass("CORE-01", "Result<int>::Ok");
  }

  {
    auto err = Result<int>::Err(ErrorCode::kNotAvailable);
    if (err.HasValue() || err.Error() != ErrorCode::kNotAvailable) {
      return Fail("CORE-02", "Result<int>::Err");
    }
    Pass("CORE-02", "Result<int>::Err");
  }

  {
    auto ok = Result<void>::Ok();
    auto err = Result<void>::Err(ErrorCode::kBusy);
    if (!ok.HasValue() || err.HasValue() || err.Error() != ErrorCode::kBusy) {
      return Fail("CORE-03", "Result<void>");
    }
    Pass("CORE-03", "Result<void>");
  }

  {
    const auto name = gf_ara::core::ToString(ErrorCode::kTimeout);
    if (std::string(name) != "Timeout") {
      return Fail("CORE-04", "ToString");
    }
    Pass("CORE-04", "ToString Timeout");
  }

  std::cout << "gf_core_smoke OK\n";
  return EXIT_SUCCESS;
}
