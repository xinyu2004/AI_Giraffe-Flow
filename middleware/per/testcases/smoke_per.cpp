#include "gf_ara/per/key_value_storage.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

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

  const auto dir = fs::temp_directory_path() / "gf_per_smoke";
  fs::remove_all(dir);
  fs::create_directories(dir);
  ::setenv("GF_PER_DIR", dir.string().c_str(), 1);

  auto& kv = KeyValueStorage::Instance();
  kv.ResetForTest();

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

  // Persist across Close/Open (dual-slot file).
  kv.Close();
  if (!kv.Open("sku_demo").HasValue()) {
    return Fail("PER-04", "re-Open");
  }
  const auto again = kv.GetValue("trim");
  if (!again.HasValue() || again.Value() != "afc_with_uss") {
    return Fail("PER-04", "persist across reopen");
  }
  Pass("PER-04", "dual-slot persist across Close/Open");

  fs::remove_all(dir);
  std::cout << "gf_per_smoke OK\n";
  return 0;
}
