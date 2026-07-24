# aur-action
维护 AUR 软件包的自动更新脚本。

## Intel-XPU
- `intel-xpumanager-bin`：Intel(R) XPU Manager 的二进制包。该工具用于监控与管理 Intel 数据中心 GPU，支持本地 CLI 与远程 RESTful 接口，功能涵盖设备信息、遥测、固件更新、诊断与配置等。
- `intel-xpu-smi-bin`：Intel(R) XPU System Management Interface 的二进制包（XPU-SMI）。它是无守护进程版本，仅提供本地接口，功能范围是 XPU Manager 的子集。

> 注意：XPU-SMI 与 XPU Manager 不能在同一系统上同时安装或运行，存在资源冲突。

### 上游来源与版本跟踪
- 上游发布：[intel/xpumanager Releases](https://github.com/intel/xpumanager/releases)
- 发行包来源：从上游发布的二进制安装包中更新 AUR PKGBUILD 版本
- 设备与系统支持：面向 Intel 数据中心 GPU（Flex/Max/Arc B 系列），支持多发行版 Linux（含 Ubuntu 20.04/22.04/24.04 等）

### 更新逻辑（来自代码）
- 脚本：`scripts/xpu.py`
- 数据源：`https://api.github.com/repos/intel/xpumanager/releases`
- 资产选择：匹配 `xpu-smi_<version>-<build>.24.04_amd64.deb`
- PKGBUILD 更新：替换 `pkgver`、`_buildver`，重置 `pkgrel=1`，并将 `sha256sums` 设为 `SKIP`
- XPU Manager 2.x 不再发布 daemon 包，因此 `intel-xpumanager-bin` 跟踪最后一个 daemon 版本 1.3.7；2.x 仅自动更新 `intel-xpu-smi-bin`。
- XPU-SMI 2.x 需要 `libigsc.so.1`；Arch 的 `igsc` 提供该 SONAME 后才会推送更新。
