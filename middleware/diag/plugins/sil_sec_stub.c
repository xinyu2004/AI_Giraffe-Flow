#include "gf_ara/diag/security_plugin.h"

#include <stddef.h>
#include <stdint.h>

static int request_seed(uint8_t level, uint8_t* seed, size_t* seed_len, size_t seed_cap) {
  (void)level;
  if (seed_cap < 2) {
    return 0x31;
  }
  seed[0] = 0xAA;
  seed[1] = 0x55;
  *seed_len = 2;
  return 0;
}

static int verify_key(uint8_t level, const uint8_t* key, size_t key_len) {
  (void)level;
  if (key_len < 2) {
    return 0x13;
  }
  return (key[0] == 0x55 && key[1] == 0xAA) ? 0 : 0x35;
}

static int authenticate(const uint8_t* req, size_t req_len, uint8_t* resp, size_t* resp_len,
                        size_t resp_cap) {
  if (req_len < 2 || resp_cap < 2) {
    return 0x13;
  }
  resp[0] = 0x69;
  resp[1] = req[1];
  *resp_len = 2;
  return 0;
}

static const GfDiagSecPlugin kPlugin = {
    GF_DIAG_SEC_ABI_VERSION,
    request_seed,
    verify_key,
    authenticate,
};

const GfDiagSecPlugin* gf_diag_sec_get_plugin(void) { return &kPlugin; }
