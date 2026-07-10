# 移植性 / OSAL / HAL / 多架构

- **主目标：** ARM Linux（aarch64 / armv7）
- **预留：** MIPS、RISC-V — `middleware/osal/arch/{mips,riscv}/`
- **构建：** `-DGF_OSAL_ARCH=arm|mips|riscv`

POSIX 共性：`middleware/osal/src/posix/`。

换板：OSAL arch + HAL + deploy profile，不改业务。

见 [DESIGN.md §10](DESIGN.md)。
