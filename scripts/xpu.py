import requests
import re
import os
import sys

# 目标仓库配置
PACKAGES = ["intel-xpumanager-bin", "intel-xpu-smi-bin"]
REPO_API = "https://api.github.com/repos/intel/xpumanager/releases/latest"

def get_latest_info():
    print("Fetching latest release info...")
    try:
        resp = requests.get(REPO_API)
        resp.raise_for_status() # 检查 HTTP 错误
        data = resp.json()
    except Exception as e:
        print(f"Network error: {e}")
        sys.exit(1)
    
    # 寻找符合 ubuntu 24.04 的 amd64 包
    # 文件名示例: xpumanager_1.3.5_20251216.170635.605ff78d.u24.04_amd64.deb
    target_asset_name = None
    download_url = None
    
    for asset in data['assets']:
        if "xpumanager" in asset['name'] and "u24.04_amd64.deb" in asset['name']:
            target_asset_name = asset['name']
            download_url = asset['browser_download_url']
            break
            
    if not target_asset_name:
        print("Could not find matching u24.04 asset in the latest release.")
        print("Available assets: " + ", ".join([a['name'] for a in data['assets']]))
        sys.exit(1)

    print(f"Found asset: {target_asset_name}")

    # 使用 split 分割字符串，而不是复杂的正则
    # 预期结构: [名称]_[版本]_[构建号]_[架构后缀]
    # 示例: xpumanager_1.3.5_20251216.170635.605ff78d.u24.04_amd64.deb
    try:
        parts = target_asset_name.split('_')
        # parts[0] -> xpumanager
        # parts[1] -> 1.3.5 (版本号)
        # parts[2] -> 20251216.170635.605ff78d.u24.04 (构建号)
        # parts[3] -> amd64.deb
        
        if len(parts) < 4:
            raise ValueError(f"Filename format unexpected: {parts}")

        version = parts[1]
        build_ver = parts[2]
        
        print(f"Parsed -> Version: {version}, Build: {build_ver}")
        return version, build_ver

    except Exception as e:
        print(f"Could not parse build version from {target_asset_name}")
        print(f"Error details: {e}")
        sys.exit(1)

def update_pkgbuild(pkg_path, new_ver, new_build_ver):
    pkgbuild_file = os.path.join(pkg_path, "PKGBUILD")
    
    if not os.path.exists(pkgbuild_file):
        print(f"Error: {pkgbuild_file} not found.")
        return False

    with open(pkgbuild_file, 'r') as f:
        content = f.read()

    # 1. 获取本地 PKGBUILD 中的版本
    ver_match = re.search(r'^pkgver=([^\s]+)', content, re.MULTILINE)
    build_match = re.search(r'^_buildver=([^\s]+)', content, re.MULTILINE)

    if not ver_match or not build_match:
        print(f"Error: Could not parse current version in {pkgbuild_file}")
        return False

    current_ver = ver_match.group(1)
    current_build = build_match.group(1)

    # 2. 对比版本
    if current_ver == new_ver and current_build == new_build_ver:
        print(f"[{pkg_path}] Already up to date ({current_ver}-{current_build}). Skipping.")
        return False

    print(f"[{pkg_path}] Update detected: {current_ver} -> {new_ver} ({new_build_ver})")

    # 3. 执行修改
    content = re.sub(r'^pkgver=.+$', f'pkgver={new_ver}', content, flags=re.MULTILINE)
    content = re.sub(r'^_buildver=.+$', f'_buildver={new_build_ver}', content, flags=re.MULTILINE)
    content = re.sub(r'^pkgrel=.+$', 'pkgrel=1', content, flags=re.MULTILINE)
    # 重置校验和为 SKIP
    content = re.sub(r"^sha256sums=\('.*'\)", "sha256sums=('SKIP')", content, flags=re.MULTILINE)

    with open(pkgbuild_file, 'w') as f:
        f.write(content)
    
    return True

if __name__ == "__main__":
    ver, build_ver = get_latest_info()
    
    any_updated = False
    for pkg in PACKAGES:
        if os.path.exists(pkg):
            if update_pkgbuild(pkg, ver, build_ver):
                any_updated = True
    
    # 输出 Action 变量
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            if any_updated:
                f.write("updated=true\n")
                f.write(f"version={ver}\n")
            else:
                f.write("updated=false\n")
    else:
        # 本地测试用
        print(f"Output: updated={str(any_updated).lower()}, version={ver}")