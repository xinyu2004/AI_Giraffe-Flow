#ifndef GF_ARA_DIAG_SECURITY_PLUGIN_H
#define GF_ARA_DIAG_SECURITY_PLUGIN_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** C ABI for OEM 0x27 / 0x29 plugins (.so / .dll). */

#define GF_DIAG_SEC_ABI_VERSION 1

typedef struct GfDiagSecPlugin {
  uint32_t abi_version;
  /** 0x27: fill seed for level; return 0 ok, else NRC byte */
  int (*request_seed)(uint8_t level, uint8_t* seed, size_t* seed_len, size_t seed_cap);
  /** 0x27: verify key; return 0 ok, else NRC byte */
  int (*verify_key)(uint8_t level, const uint8_t* key, size_t key_len);
  /** 0x29 stub: return 0 ok, else NRC; role out optional */
  int (*authenticate)(const uint8_t* req, size_t req_len, uint8_t* resp, size_t* resp_len,
                      size_t resp_cap);
} GfDiagSecPlugin;

/** Exported by plugin: returns pointer to static descriptor. */
typedef const GfDiagSecPlugin* (*GfDiagSecGetPluginFn)(void);

#define GF_DIAG_SEC_GET_PLUGIN "gf_diag_sec_get_plugin"

#ifdef __cplusplus
}
#endif

#endif
