#include "gf_ara/per/key_value_storage.hpp"

#include <iostream>

namespace {

int Fail(const char* id, const char* msg) {
  std::cerr << "CASE " << id << " FAIL " << msg << '\n';
  return 1;
}

void Pass(const char* id, const char* detail) {
  std::cout << "CASE " << id << " PASS " << detail << '\n';
}

}  // namespace

int main() {
  using gf_ara::per::KeyValueStorage;

  auto& kv = KeyValueStorage::Instance();
  kv.Clear();

  if (!kv.Open("sku_demo").HasValue()) {
    return Fail("PER-01", "Open");
  }
  Pass("PER-01", "Open instance=sku_demo");

  if (!kv.SetValue("trim", "afc_with_uss").HasValue()) {
    return Fail("PER-02", "SetValue");
  }
  const auto got = kv.GetValue("trim");
  if (!got.HasValue() || got.Value() != "afc_with_uss") {
    return Fail("PER-02", "GetValue mismatch");
  }
  Pass("PER-02", "SetValue/GetValue roundtrip");

  if (kv.GetValue("missing").HasValue()) {
    return Fail("PER-03", "missing key should Err");
  }
  Pass("PER-03", "missing key → NotAvailable");

  std::cout << "gf_per_smoke OK\n";
  return 0;
}
