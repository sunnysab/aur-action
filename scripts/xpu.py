# scripts/xpu.py
import requests
import re
import os
import sys

# 目标仓库配置
PACKAGES = ["intel-xpumanager-bin", "intel-xpu-smi-bin"]
REPO_API = "https://api.github.com/repos/intel/xpumanager/releases/latest"

def get_latest_info():
    print("Fetching latest release info...")
    resp = requests.get(REPO_API)
    if resp.status_code != 200:
        print(f"Failed to fetch release: {resp.status_code}")
        sys.exit(1)
    
    data = resp.json()
    tag_name = data['tag_name'].lstrip('v') # 例如 1.3.5
    
    # 寻找符合 ubuntu 24.04 的 amd64 包，以此提取 build 版本
    # 文件名示例: xpumanager_1.3.5_20251216.170635.605ff78d.u24.04_amd64.deb
    target_asset = None
    for asset in data['assets']:
        if "xpumanager" in asset['name'] and "u24.04_amd64.deb" in asset['name']:
            target_asset = asset['name']
            break
            
    if not target_asset:
        print("Could not find matching u24.04 asset.")
        sys.exit(1)

    # 正则提取 buildver (中间那长串)
    # 匹配: _1.3.5_(20251216.170635.605ff78d.u24.04)_amd64.deb
    match = re.search(fr"_{re.escape(tag_name)}_(.+?)_amd64\.deb", target_asset)
    if not match:
        print(f"Could not parse build version from {target_asset}")
        sys.exit(1)
        
    build_ver = match.group(1)
    return tag_name, build_ver

def update_pkgbuild(pkg_path, new_ver, new_build_ver):
    pkgbuild_file = os.path.join(pkg_path, "PKGBUILD")
    
    if not os.path.exists(pkgbuild_file):
        print(f"Error: {pkgbuild_file} not found.")
        return False

    with open(pkgbuild_file, 'r') as f:
        content = f.read()

    # 1. 获取本地 PKGBUILD 中的版本
    # 使用正则精确提取，防止提取到注释里的数字
    ver_match = re.search(r'^pkgver=([^\s]+)', content, re.MULTILINE)
    build_match = re.search(r'^_buildver=([^\s]+)', content, re.MULTILINE)

    if not ver_match or not build_match:
        print(f"Error: Could not parse current version in {pkgbuild_file}")
        return False

    current_ver = ver_match.group(1)
    current_build = build_match.group(1)

    # 2. 完全相等则直接退出
    # 只有当 主版本号不同 OR 构建版本号不同 时，才继续
    if current_ver == new_ver and current_build == new_build_ver:
        print(f"[{pkg_path}] Already up to date ({current_ver}-{current_build}). Skipping.")
        return False

    print(f"[{pkg_path}] Update detected: {current_ver} -> {new_ver}")

    # 3. 执行修改
    content = re.sub(r'^pkgver=.+$', f'pkgver={new_ver}', content, flags=re.MULTILINE)
    content = re.sub(r'^_buildver=.+$', f'_buildver={new_build_ver}', content, flags=re.MULTILINE)
    content = re.sub(r'^pkgrel=.+$', 'pkgrel=1', content, flags=re.MULTILINE)
    content = re.sub(r"^sha256sums=\('.*'\)", "sha256sums=('SKIP')", content, flags=re.MULTILINE)

    with open(pkgbuild_file, 'w') as f:
        f.write(content)
    
    return True

if __name__ == "__main__":
    ver, build_ver = get_latest_info()
    print(f"Latest Version: {ver}, Build: {build_ver}")

    any_updated = False
    for pkg in PACKAGES:
        if os.path.exists(pkg):
            if update_pkgbuild(pkg, ver, build_ver):
                any_updated = True
    
    # 利用 GITHUB_OUTPUT 传递状态给后续步骤
    if any_updated:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("updated=true\n")
            f.write(f"version={ver}\n")
    else:
        print("All packages are up-to-date.")