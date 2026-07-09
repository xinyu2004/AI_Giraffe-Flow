#ifndef GF_ARA_CORE_RESULT_HPP
#define GF_ARA_CORE_RESULT_HPP

namespace gf_ara::core {

template <typename T>
class Result {
 public:
  static Result Ok(T value) {
    Result r;
    r.ok_ = true;
    r.value_ = std::move(value);
    return r;
  }
  static Result Err() {
    Result r;
    r.ok_ = false;
    return r;
  }
  [[nodiscard]] bool HasValue() const { return ok_; }
  [[nodiscard]] const T& Value() const { return value_; }

 private:
  bool ok_{false};
  T value_{};
};

template <>
class Result<void> {
 public:
  static Result Ok() {
    Result r;
    r.ok_ = true;
    return r;
  }
  static Result Err() {
    Result r;
    r.ok_ = false;
    return r;
  }
  [[nodiscard]] bool HasValue() const { return ok_; }

 private:
  bool ok_{false};
};

}  // namespace gf_ara::core

#endif
