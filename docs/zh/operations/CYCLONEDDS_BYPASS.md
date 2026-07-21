# P2 B 轨：CycloneDDS 与主链边界

> 配套：`scripts/smoke_bd_cyclone.sh` · `cmake/profiles/bd_cyclone.cmake`  
> 钉扎：`deps/versions.lock.md` → **cyclonedds 0.10.5**

## 结论

| 通道 | P2 角色 | 说明 |
|------|---------|------|
| **iceoryx** | **主链 SIL** | `afc_with_uss` 四进程 / 双进程 demo；`smoke_sil*.sh` |
| **CycloneDDS** | **旁路真收发** | binding 真 pub/sub ≥1 event；**不**替换主链 |
| **vsomeip** | **保持 stub** | `middleware/bindings/someip`；真源码/Boost 后置 |

## 怎么跑

```bash
# 拉源码（与 iceoryx 同一 bootstrap）
bash scripts/bootstrap_deps.sh

# 真 DDS smoke（独立 build 目录，不碰 build/ iceoryx SIL）
bash scripts/smoke_bd_cyclone.sh
```

期望输出含：`backend=cyclonedds` 与 `gf_dds_binding_smoke OK`。

离线 stub（无 third_party）：

```bash
bash scripts/smoke_bd_stub.sh   # GF_DDS_BACKEND=stub
```

## 配置开关

| CMake | 含义 |
|-------|------|
| `GF_WITH_DDS=ON` | 编入 dds binding |
| `GF_DDS_BACKEND=cyclone` | 链 `ddsc` + idlc `GfBlob.idl` |
| `GF_DDS_BACKEND=stub` | 进程内 TopicBus（CI 默认） |

SKU `req.bindings` 可勾 `dds`，但 **AFC 主链进程仍走 iceoryx**；DDS 用于跨机/旁路演示。

## 与 O/F

录包 / Foxglove 当前从 **iceoryx SIL 日志** 取 session；DDS smoke 不进入该路径。
