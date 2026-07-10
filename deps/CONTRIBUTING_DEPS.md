# How to change dependencies

## Policy (P0+, do not regress)

| 类别 | 策略 |
|------|------|
| **runtime_board**（iceoryx、attr、acl、日后 vsomeip…） | **钉扎 + 源码**，用**当前工具链**编进 `middleware/.deps-prefix/` 或 CMake `add_subdirectory`。主机与交叉同一路径，只换 `GF_CROSS_PREFIX` / `CMAKE_TOOLCHAIN_FILE`。 |
| **host_tools**（cmake、g++、git、python、cantools） | 可用系统包 / pip；**不上板**。 |
| **apt 的 `*-dev`（如 libacl1-dev）** | **仅开发机可选捷径，不是产品路径。** 板端 rootfs 要的是运行库（或静态链进产物），由我们 staging/镜像打包，不在板子上 `apt install *-dev`。 |

板子上通常**没有**、也不该依赖 `libacl1-dev`。交叉时用同一套 attr/acl 源码 + `aarch64-linux-gnu-gcc` 装进 `middleware/.deps-prefix`，再编 iceoryx。

## 变更步骤

1. **Propose in `DEPENDENCIES.yaml`** — id, purpose, license, category.
2. **License check** — SPDX OK for vehicle if `runtime_board`.
3. **Pin** — exact tag/SHA in `versions.lock.md`.
4. **Integrate** — `source_staging`（bootstrap → `middleware/.deps-prefix`）或 CMake `add_subdirectory` / FetchContent；**不要**把「只在某台机器 apt 装过」当成集成方式。
5. **Profiles** — which of `desktop` / `board` / `vehicle-debug` / `production`.
6. **Board CI** — host UI / ROS desktop deps must not enter board cross-builds.

Do **not** add undocumented packages only inside a single `CMakeLists.txt`.
