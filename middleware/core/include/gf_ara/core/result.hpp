#ifndef GF_ARA_CORE_RESULT_HPP
#define GF_ARA_CORE_RESULT_HPP

#include "gf_ara/core/error_code.hpp"

#include <utility>

namespace gf_ara::core {

template <typename T>
class Result {
 public:
  static Result Ok(T value) {
    Result r;
    r.ok_ = true;
    r.value_ = std::move(value);
    r.error_ = ErrorCode::kOk;
    return r;
  }

  static Result Err(ErrorCode error = ErrorCode::kUnknown) {
    Result r;
    r.ok_ = false;
    r.error_ = error;
    return r;
  }

  [[nodiscard]] bool HasValue() const noexcept { return ok_; }
  [[nodiscard]] explicit operator bool() const noexcept { return ok_; }

  [[nodiscard]] const T& Value() const& { return value_; }
  [[nodiscard]] T& Value() & { return value_; }
  [[nodiscard]] T&& Value() && { return std::move(value_); }

  [[nodiscard]] ErrorCode Error() const noexcept { return error_; }

 private:
  bool ok_{false};
  ErrorCode error_{ErrorCode::kUnknown};
  T value_{};
};

template <>
class Result<void> {
 public:
  static Result Ok() {
    Result r;
    r.ok_ = true;
    r.error_ = ErrorCode::kOk;
    return r;
  }

  static Result Err(ErrorCode error = ErrorCode::kUnknown) {
    Result r;
    r.ok_ = false;
    r.error_ = error;
    return r;
  }

  [[nodiscard]] bool HasValue() const noexcept { return ok_; }
  [[nodiscard]] explicit operator bool() const noexcept { return ok_; }
  [[nodiscard]] ErrorCode Error() const noexcept { return error_; }

 private:
  bool ok_{false};
  ErrorCode error_{ErrorCode::kUnknown};
};

}  // namespace gf_ara::core

#endif
