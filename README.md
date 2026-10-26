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
- XPU-SMI 2.0–2.2 需要 `libigsc.so.1`，由本仓库维护的 `intel-igsc` 提供（Arch 官方 `igsc` 只有 `libigsc.so.0`）；2.3.0 起上游已把 igsc 与 metee 静态编入二进制，不再有任何动态依赖，`package()` 里的路径搬移与 patchelf 改写也随之删除。

> 2.0–2.2 直接链接 `libmetee`，而上游的 Ubuntu 构建针对的是 Ubuntu 自带的 SONAME（如 `libmetee.so.6.2.5.0`），因此当时需要在 `package()` 中用 patchelf 改写为构建机上实际的 SONAME。

## Intel-IGSC
- `intel-igsc`：Intel Graphics System Controller 固件更新库，提供 `igsc` CLI 与 `libigsc.so.1`。

Arch 官方 `extra/igsc` 停留在上游 0.9.5，只提供 `libigsc.so.0`，且自 2025-09 起被标记为过期（此后提交均为跟随 `intel-metee` 的 rebuild），无法满足 XPU-SMI 2.0–2.2 的依赖，因此另建此包跟踪上游源码发布。

### 上游来源与版本跟踪
- 上游发布：[intel/igsc Releases](https://github.com/intel/igsc/releases)
- 版本来源：GitHub release tag（`V1.3.2` → `1.3.2`），从源码 tarball 构建
- 依赖与冲突：`provides=('igsc=<pkgver>' 'libigsc.so=1-64')`、`conflicts=('igsc')`，安装前需移除官方 `igsc`

### 更新逻辑（来自代码）
- tag 选择：仅匹配稳定的 `V<version>` tag，跳过 prerelease 与 draft
- PKGBUILD 更新：替换 `pkgver`，重置 `pkgrel=1`，并将 `sha256sums` 设为 `SKIP`

> `libmetee` 的 SONAME 携带完整版本号（例如 `libmetee.so.6.2.6.0`），上游每发一个小版本都会让已构建的 `libigsc.so.1` 找不到依赖，届时需要重新构建本包。

## ThinkWatch Lite
- `thinkwatch-lite-bin`：ThinkWatch Lite 的二进制包。它是 Claude Code、Codex 等客户端的本地网关：客户端只接网关一次，之后换上游、换模型都不用改客户端配置。

### 上游来源与版本跟踪
- 上游发布：[ThinkWatchProject/ThinkWatch-Lite Releases](https://github.com/ThinkWatchProject/ThinkWatch-Lite/releases)
- 上游只发 AppImage（x86_64/aarch64）与安装脚本，没有源码包
- 版本来源：GitHub release tag（`v2026.10.1` → `2026.10.1`），取其中的 x86_64 AppImage 解包后重新打包

### 更新逻辑（来自代码）
- tag 选择：仅匹配稳定的 `v<version>` tag，跳过 prerelease 与 draft
- 资产选择：从 release 的资产里挑 `*-x86_64.AppImage`（名字由 release 读出，上游在 2026.10.2 加过 `linux-` 前缀），该资产还没上传完的 release 直接跳过，否则会推出一个下不了源的 PKGBUILD
- PKGBUILD 更新：替换 `pkgver`，重置 `pkgrel=1`，将 `sha256sums` 设为 `SKIP`，并按 release 里的真实资产名重写 `_asset=`；CI 的 `updpkgsums` 再填真实校验和

### 打包要点
- 上游 AppImage 过去带着构建发行版的 `libwayland-client/egl/server/cursor`。在 Arch（Mesa 26 + wayland 1.26）上，WebKitGTK 让 Mesa 建 EGL display 时会加载到这份旧库，`EGL_BAD_PARAMETER` 直接 abort 掉 web process，窗口白屏。2026.10.9 的上游 AppImage 已不再附带这几个库，`build()` 里的删除保留作为回归防线。
- 解包安装后 `$APPIMAGE` 为空，应用自认为开发构建、不再自更新，更新由 pacman 负责。
- `thinkwatch://` 登录回调需要一次性执行 `xdg-mime default app.thinkwatch.lite.desktop x-scheme-handler/thinkwatch`。

## ThinkWatch Core
- `thinkwatch-core-bin`：ThinkWatch Core 的二进制包，即 `twcore` 的服务端版本。它是 ThinkWatch Lite 内置的那套网关引擎，单独跑在 Linux 服务器上，接受 Lite 或其他客户端的远程连接。

### 上游来源与版本跟踪
- 上游发布：[ThinkWatchProject/ThinkWatch-Core Releases](https://github.com/ThinkWatchProject/ThinkWatch-Core/releases)
- 资产：`twcore-x86_64-unknown-linux-gnu.tar.gz`（另有 aarch64 与裸二进制），里面是 `twcore`、`twcore.service` 与 `LICENSE`
- 版本来源：GitHub release tag（`v0.83.2` → `0.83.2`）

### 更新逻辑（来自代码）
- tag 选择：仅匹配稳定的 `v<version>` tag，跳过 prerelease 与 draft；release 里还没传 x86_64 tar.gz 的整条跳过
- PKGBUILD 更新：替换 `pkgver`，重置 `pkgrel=1`，`sha256sums` 设为 `SKIP`，其余不动；CI 的 `updpkgsums` 再填真实校验和
- 资产名不带版本，所以 `source=` 写成 `"$pkgver-$_tarball::…"`：同一个构建目录里前后两个版本不会落到同一个文件名上，否则第二次构建会撞上旧文件的校验和

### 打包要点
- 运行时依赖只有 `glibc` 与 `gcc-libs`；上游要求 glibc 2.35+（Ubuntu 22.04 / Debian 12 及以上）
- 上游 unit 的 `ExecStart=/usr/local/bin/twcore` 是 install.sh 的安装路径，包里改写为 `/usr/bin/twcore`；`StateDirectory=/var/lib/thinkwatch` 保持不变，`EnvironmentFile=-/etc/thinkwatch/env` 由管理员按需自建
- unit 以 `thinkwatch` 用户运行，本包用 `sysusers.d` 建这个账号（上游只有 install.sh 会建）；包本身不启用服务，首次配置见上游 `docs/server.md`
- 装完后更新交给 pacman：`twcore upgrade` 会自己从 GitHub 替换正在运行的二进制，那是绕开包管理器的另一条路径
- 改配置要用服务用户跑：`sudo -u thinkwatch env THINKWATCH_HOME=/var/lib/thinkwatch twcore …`。直接用 `sudo twcore … --config /var/lib/thinkwatch/config.yaml` 会把 `config.yaml` 重写成 `root:root 600`，之后服务（用户 `thinkwatch`）读不到、配置不生效、重启还会崩在 `Permission denied`

## CI

`.github/workflows/aur.yml` 每天检查上游并在有更新时提交到 AUR。推送前会对每个待更新的包跑一次 `makepkg -f -d --nocheck -c` 冒烟构建：

- 没有这一步时，`package()` 里的错误只会在用户执行 `makepkg` 时才暴露（例如 `intel-xpu-smi-bin` 曾把 `patchelf --print-needed | grep '^libmetee\.so\.'` 留在 `package()` 中，2.3.0 静态链接 metee 后该 `grep` 空匹配返回 1，被 `set -e` 直接中断，包根本无法构建）。
- `-d` 只跳过依赖校验：冒烟构建验证的是 PKGBUILD 自身能否走完 `build()`/`package()`，而容器里没有这些包的运行时依赖。相应地，容器必须预装各包的 `makedepends`（当前为 `cmake` 与 `intel-metee`，供 `intel-igsc` 从源码构建使用）。
