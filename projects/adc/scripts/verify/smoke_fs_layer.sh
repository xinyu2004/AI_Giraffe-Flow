#!/usr/bin/env bash
# Host smoke: Empty180 baseline/occ restore + pack.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BUILD_SIL="${GF_BUILD_DIR:-${ROOT}/projects/adc/build-sil}"
CCJSON="${BUILD_SIL}/compile_commands.json"
if [[ ! -f "${CCJSON}" ]]; then
  echo "missing ${CCJSON}; compile SIL first" >&2
  exit 1
fi
python3 - "${CCJSON}" <<'PY'
import json, subprocess, sys, textwrap
cc = json.load(open(sys.argv[1]))
cmd = next(e["command"] for e in cc if e.get("file", "").endswith("driving_plus/src/main.cpp"))
flags = []
parts = cmd.split()
i = 0
while i < len(parts):
    p = parts[i]
    if p.startswith(("-I", "-isystem", "-D", "-std")):
        flags.append(p)
        if p in ("-I", "-isystem", "-D") and i + 1 < len(parts) and not parts[i + 1].startswith("-"):
            flags.append(parts[i + 1])
            i += 1
    i += 1
src = textwrap.dedent(r"""
#include "fs/fs_empty180.hpp"
#include <cstdio>
using namespace gf_plan_fs;
static int fail(const char* m){ std::fprintf(stderr,"FAIL %s\n",m); return 1; }
int main(){
  FsEmpty180 base{};
  FsBaselineFromOpticsFsd(&base, nullptr, nullptr, 0, 80.f);
  if(!base.valid) return fail("baseline");
  float r0 = base.r[0];
  FsOccSample o{}; o.x_m=20; o.y_m=0; o.half_w_m=4; o.half_l_m=2;
  FsEmpty180 act=base;
  bool hit[kFsEmptyN]{};
  FsOccApply180(&act, &o, 1, hit);
  bool shorter=false;
  for(int i=0;i<kFsEmptyN;++i) if(act.r[i]+0.2f<base.r[i]) shorter=true;
  if(!shorter) return fail("occ no shorten");
  FsOccRestoreBins(&act, base, hit);
  for(int i=0;i<kFsEmptyN;++i){
    if(hit[i] && std::fabs(act.r[i]-base.r[i])>1e-3f) return fail("restore");
  }
  GroundPoly p=FsPack180ToPoly(act);
  if(!p.valid || p.n!=kFsEmptyN) return fail("pack");
  // Rabbit ear: host-lane box shortens center more than FOV-edge miss bins.
  FsEmpty180 ear_base{};
  FsBaselineFromOpticsFsd(&ear_base, nullptr, nullptr, 0, 120.f);
  FsEmpty180 ear=ear_base;
  bool hit2[kFsEmptyN]{};
  FsOccSample car{}; car.x_m=25.f; car.y_m=0.f; car.half_l_m=2.25f; car.half_w_m=0.95f;
  FsOccApply180(&ear, &car, 1, hit2);
  float r_c=1e9f, r_e=0.f;
  for(int i=0;i<kFsEmptyN;++i){
    float a=FsBinAngRad(i);
    if(!FsInFrontFov(a)) continue;
    float ca=std::cos(a);
    // Center vs FOV lip (front half≈50° → ca≳0.64).
    if(ca>0.98f) r_c=std::min(r_c, ear.r[i]);
    if(ca>0.64f && ca<0.75f) r_e=std::max(r_e, ear.r[i]);
  }
  if(!(r_e > r_c + 3.f)) return fail("ears");
  // Chord clip: pull longer forward ray toward shorter (no ego dig / no rear touch).
  {
    RoadEdgePoly L{}, R{};
    L.valid = true; L.c0 = 1.75f; L.c1 = 0.f; L.c2 = -0.004f; L.c3 = 0.f; L.vr_m = 80.f;
    R.valid = true; R.c0 = -1.75f; R.c1 = 0.f; R.c2 = -0.004f; R.c3 = 0.f; R.vr_m = 80.f;
    auto count_bad = [&](const FsEmpty180& e) {
      int bad = 0;
      for (int i = 0; i < kFsEmptyN; ++i) {
        const int j = (i + 1) % kFsEmptyN;
        const float ai = FsBinAngRad(i), aj = FsBinAngRad(j);
        if (FsInRearFov(ai) || FsInRearFov(aj)) continue;
        const float cai = std::cos(ai), caj = std::cos(aj);
        if (cai < 0.05f || caj < 0.05f) continue;
        const float xa = e.r[i] * cai, ya = e.r[i] * std::sin(ai);
        const float xb = e.r[j] * caj, yb = e.r[j] * std::sin(aj);
        if (!FsChordInLaneCorridor(xa, ya, xb, yb, L, R, nullptr, 0, 10)) ++bad;
      }
      return bad;
    };
    FsEmpty180 curved{};
    FsBaselineFromOpticsFsd(&curved, nullptr, nullptr, 0, 80.f);
    FsRestrictLane180(&curved, L, R, nullptr, 0);
    const int bad0 = count_bad(curved);
    FsClipEmpty180ChordsToLane(&curved, L, R, nullptr, 0);
    const int bad1 = count_bad(curved);
    if (bad0 > 0 && !(bad1 < bad0)) return fail("chord clip no improve");
    if (bad1 > bad0) return fail("chord worse");
    // Plant classic ear: short Restrict neighbor + far optical bin.
    int i_short = -1, i_long = -1;
    for (int i = 0; i < kFsEmptyN; ++i) {
      const int j = (i + 1) % kFsEmptyN;
      if (std::cos(FsBinAngRad(i)) < 0.2f || std::cos(FsBinAngRad(j)) < 0.2f) continue;
      if (FsInRearFov(FsBinAngRad(i)) || FsInRearFov(FsBinAngRad(j))) continue;
      if (curved.r[i] < 15.f && curved.r[j] > 40.f) { i_short = i; i_long = j; break; }
      if (curved.r[j] < 15.f && curved.r[i] > 40.f) { i_short = j; i_long = i; break; }
    }
    if (i_long >= 0) {
      const float r_short = curved.r[i_short];
      curved.r[i_long] = 80.f;
      FsClipEmpty180ChordsToLane(&curved, L, R, nullptr, 0);
      if (curved.r[i_long] > r_short * 1.5f + 2.f) return fail("long ear not pulled");
      if (curved.r[i_short] + 0.2f < r_short) return fail("short end dug");
    }
    FsEmpty180 rear_chk{};
    FsBaselineFromOpticsFsd(&rear_chk, nullptr, nullptr, 0, 80.f);
    FsRestrictLane180(&rear_chk, L, R, nullptr, 0);
    float r_rear0 = 0.f;
    for (int i = 0; i < kFsEmptyN; ++i) {
      if (FsInRearFov(FsBinAngRad(i))) r_rear0 = std::max(r_rear0, rear_chk.r[i]);
    }
    FsClipEmpty180ChordsToLane(&rear_chk, L, R, nullptr, 0);
    float r_rear1 = 0.f;
    for (int i = 0; i < kFsEmptyN; ++i) {
      if (FsInRearFov(FsBinAngRad(i))) r_rear1 = std::max(r_rear1, rear_chk.r[i]);
    }
    if (r_rear1 + 0.5f < r_rear0) return fail("rear dug by chord clip");
  }
  std::printf("OK empty180 r0=%.1f poly_n=%d ear_c=%.1f ear_e=%.1f\n", r0, p.n, r_c, r_e);
  return 0;
}
""")
open("/tmp/fs_e180_smoke.cpp","w").write(src)
subprocess.check_call(["g++","-std=c++17","-O0",*flags,"/tmp/fs_e180_smoke.cpp","-o","/tmp/fs_e180_smoke"])
rc = subprocess.call(["/tmp/fs_e180_smoke"])
if rc != 0:
    raise SystemExit(rc)
dig = textwrap.dedent(r"""
#include "fs/fs_empty180.hpp"
#include <cstdio>
using namespace gf_plan_fs;
int main(){
  FsEmpty180 b{};
  FsBaselineFromOpticsFsd(&b, nullptr, nullptr, 0, 120.f);
  GroundPoly p=FsPack180ToPoly(b);
  if(p.n!=kFsEmptyN){ std::fprintf(stderr,"FAIL dig poly_n=%d\n", p.n); return 1; }
  // Surround DEBUG: 4-cam = mirrors+bumpers → front/rear bins stay covered (not dug to floor).
  int dug=0; float r_side_max=0.f;
  for(int i=0;i<kFsEmptyN;++i){
    float a=FsBinAngRad(i);
    float rr=std::hypot(p.x[i], p.y[i]);
    if(rr<0.6f) ++dug;
    else if(!FsInFrontFov(a)&&!FsInRearFov(a)) r_side_max=std::max(r_side_max, b.r[i]);
  }
  int keep_in_front_fov=0;
  for(int i=0;i<kFsEmptyN;++i){
    float a=FsBinAngRad(i);
    float rr=std::hypot(p.x[i], p.y[i]);
    if(FsInFrontFov(a) && rr>1.0f) ++keep_in_front_fov;
  }
  if(keep_in_front_fov<20){
    std::fprintf(stderr,"FAIL bumper-front should cover front FOV keep=%d\n", keep_in_front_fov);
    return 1;
  }
  float surr[kFsEmptyN];
  gf_fs_envelope::SurroundFillEmpty180(surr, gf_fs_envelope::SideLatM());
  int cov=0; float ymax=0.f;
  for(int i=0;i<kFsEmptyN;++i){
    if(surr[i]<0.5f) continue;
    ++cov;
    const float a=FsBinAngRad(i);
    ymax=std::max(ymax, std::fabs(surr[i]*std::sin(a)));
  }
  if(cov<150){ std::fprintf(stderr,"FAIL surround fill cov=%d (expect ~full ring)\n", cov); return 1; }
  if(ymax<2.0f){ std::fprintf(stderr,"FAIL surround fill |y|=%.2f\n", ymax); return 1; }
  std::printf("OK surround_dig poly_n=%d dug_floor=%d side_r_max=%.2f keep_frontFov=%d "
              "surr_cov=%d surr_|y|=%.2f\n",
              p.n, dug, r_side_max, keep_in_front_fov, cov, ymax);
  return 0;
}
""")
open("/tmp/fs_dig.cpp","w").write(dig)
subprocess.check_call(["g++","-std=c++17","-O0",*flags,"/tmp/fs_dig.cpp","-o","/tmp/fs_dig"])
import os
env = os.environ.copy()
env["GF_FS_DEBUG_REGION"] = "surround"
raise SystemExit(subprocess.call(["/tmp/fs_dig"], env=env))
PY
