# com

`gf_ara::com` — Event 子集（P0）。

当前：`EventPublisher` / `EventSubscriber` + **LoopbackBus**（同进程冒烟，无需 RouDi）。
iceoryx：同一表面接到 [`../bindings/iceoryx`](../bindings/iceoryx/)。

```bash
cmake -B build -DGF_BUILD_TESTS=ON
cmake --build build --target gf_com_loopback_smoke
./build/middleware/com/gf_com_loopback_smoke
```

Payload P0 要求 **trivially copyable**（为 iceoryx relocatable 铺路）。

Parent: [middleware/README.md](../README.md)
