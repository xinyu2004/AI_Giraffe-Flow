# third_party/ (under middleware)

上游源码检出（按 `deps/DEPENDENCIES.yaml` 的 id）。**不提交**（见 `.gitignore`）。

```bash
bash scripts/bootstrap_deps.sh
# → middleware/third_party/{attr,acl,iceoryx,cpptoml,cyclonedds,dlt-daemon}
# → middleware/.deps-prefix/   （attr/acl/cpptoml 安装前缀，同源交叉）
```

CMake：[`cmake/Dependencies.cmake`](../../cmake/Dependencies.cmake) 使用 `middleware/.deps-prefix` 的 ACL + **cpptoml**，并对 `iceoryx` / `cyclonedds` / **`dlt-daemon`** 做 `add_subdirectory`（与本仓同一 `CMAKE_TOOLCHAIN_FILE`；**非 apt**）。

**策略：** iceoryx 的 `DOWNLOAD_TOML_LIB` / googletest ExternalProject **关闭**；不要把上游依赖下到 `projects/.../build-*/dependencies/`。源码在 `third_party/`，安装产物在 `.deps-prefix/`。

DLT：见 [docs/zh/operations/DLT_PLAN.md](../../docs/zh/operations/DLT_PLAN.md)。

Related: [../../dep-manifest/README.md](../../dep-manifest/README.md) · [../../dep-manifest/versions.lock.md](../../dep-manifest/versions.lock.md)
