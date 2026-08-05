# third_party/ (under middleware)

上游源码检出（按 `deps/DEPENDENCIES.yaml` 的 id）。**不提交**（见 `.gitignore`）。

```bash
bash scripts/bootstrap_deps.sh
# → middleware/third_party/{attr,acl,iceoryx,cyclonedds,dlt-daemon}
# → middleware/.deps-prefix/   （attr/acl 安装前缀，同源交叉）
```

CMake：[`cmake/Dependencies.cmake`](../../cmake/Dependencies.cmake) 使用 `middleware/.deps-prefix` 的 ACL，并对 `iceoryx` / `cyclonedds` / **`dlt-daemon`** 做 `add_subdirectory`（与本仓同一 `CMAKE_TOOLCHAIN_FILE`；**非 apt**）。

DLT：见 [docs/zh/operations/DLT_PLAN.md](../../docs/zh/operations/DLT_PLAN.md)。

Related: [../../dep-manifest/README.md](../../dep-manifest/README.md) · [../../dep-manifest/versions.lock.md](../../dep-manifest/versions.lock.md)
