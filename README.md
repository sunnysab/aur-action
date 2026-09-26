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
- 脚本：`scripts/update.py`
- 数据源：`https://api.github.com/repos/intel/xpumanager/releases`、`https://api.github.com/repos/intel/igsc/releases`
- 资产选择：匹配 `xpu-smi_<version>-<build>.24.04_amd64.deb`
- PKGBUILD 更新：替换 `pkgver`、`_buildver`，重置 `pkgrel=1`，并将 `sha256sums` 设为 `SKIP`
- XPU Manager 2.x 不再发布 daemon 包，因此 `intel-xpumanager-bin` 跟踪最后一个 daemon 版本 1.3.7；2.x 仅自动更新 `intel-xpu-smi-bin`。
- XPU-SMI 2.x 需要 `libigsc.so.1`，由本仓库维护的 `intel-igsc` 提供（Arch 官方 `igsc` 只有 `libigsc.so.0`）。

> XPU-SMI 2.x 还直接链接 `libmetee`，而上游的 Ubuntu 构建针对的是 Ubuntu 自带的 SONAME（如 `libmetee.so.6.2.5.0`）。PKGBUILD 在 `package()` 中用 patchelf 改写为构建机上实际的 SONAME，因此 `intel-metee` 升级后需要重新构建本包。

## Intel-IGSC
- `intel-igsc`：Intel Graphics System Controller 固件更新库，提供 `igsc` CLI 与 `libigsc.so.1`。

Arch 官方 `extra/igsc` 停留在上游 0.9.5，只提供 `libigsc.so.0`，且自 2025-09 起被标记为过期（此后提交均为跟随 `intel-metee` 的 rebuild），无法满足 XPU-SMI 2.x 的依赖，因此另建此包跟踪上游源码发布。

### 上游来源与版本跟踪
- 上游发布：[intel/igsc Releases](https://github.com/intel/igsc/releases)
- 版本来源：GitHub release tag（`V1.3.2` → `1.3.2`），从源码 tarball 构建
- 依赖与冲突：`provides=('igsc=<pkgver>' 'libigsc.so=1-64')`、`conflicts=('igsc')`，安装前需移除官方 `igsc`

### 更新逻辑（来自代码）
- tag 选择：仅匹配稳定的 `V<version>` tag，跳过 prerelease 与 draft
- PKGBUILD 更新：替换 `pkgver`，重置 `pkgrel=1`，并将 `sha256sums` 设为 `SKIP`

> `libmetee` 的 SONAME 携带完整版本号（例如 `libmetee.so.6.2.6.0`），上游每发一个小版本都会让已构建的 `libigsc.so.1` 找不到依赖，届时需要重新构建本包。
