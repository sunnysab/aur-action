import json
import os
import re
import sys
from pathlib import Path
from urllib.request import urlopen


REPO_API = "https://api.github.com/repos/intel/xpumanager/releases?per_page=20"
ASSET_PATTERNS = {
    "intel-xpumanager-bin": re.compile(
        r"^xpumanager_(?P<version>\d+(?:\.\d+)+)_(?P<build>[^_]+)_amd64\.deb$"
    ),
    "intel-xpu-smi-bin": re.compile(
        r"^xpu-smi_(?P<version>\d+(?:\.\d+)+)-(?P<build>[^_]+)_amd64\.deb$"
    ),
}


def parse_asset(name):
    for package, pattern in ASSET_PATTERNS.items():
        if match := pattern.fullmatch(name):
            return package, *match.group("version", "build")
    return None


def get_latest_info():
    print("Fetching release info...")
    with urlopen(REPO_API, timeout=30) as response:
        releases = json.load(response)

    found = {}
    for release in releases:
        for asset in release.get("assets", []):
            parsed = parse_asset(asset["name"])
            if parsed and parsed[2].endswith("24.04"):
                found.setdefault(parsed[0], parsed[1:])
        if len(found) == len(ASSET_PATTERNS):
            break

    missing = ASSET_PATTERNS.keys() - found.keys()
    if missing:
        raise RuntimeError(f"No Ubuntu 24.04 asset found for: {', '.join(missing)}")
    return found


def update_pkgbuild(pkg_path, version, build):
    pkgbuild = Path(pkg_path) / "PKGBUILD"
    content = pkgbuild.read_text()

    current_version = re.search(r"^pkgver=(\S+)", content, re.MULTILINE)
    current_build = re.search(r"^_buildver=(\S+)", content, re.MULTILINE)
    if not current_version or not current_build:
        raise RuntimeError(f"Could not parse current version in {pkgbuild}")
    if (current_version.group(1), current_build.group(1)) == (version, build):
        print(f"[{pkg_path}] Already up to date ({version}-{build}).")
        return False

    print(f"[{pkg_path}] Updating to {version}-{build}")
    content = re.sub(r"^pkgver=.+$", f"pkgver={version}", content, flags=re.MULTILINE)
    content = re.sub(r"^_buildver=.+$", f"_buildver={build}", content, flags=re.MULTILINE)
    content = re.sub(r"^pkgrel=.+$", "pkgrel=1", content, flags=re.MULTILINE)
    if Path(pkg_path).name == "intel-xpu-smi-bin":
        content = re.sub(
            r"xpu-smi_\$\{pkgver\}[_-]\$\{_buildver\}_amd64\.deb",
            "xpu-smi_${pkgver}-${_buildver}_amd64.deb",
            content,
        )
        content = content.replace("data.tar.gz", "data.tar.zst")
        content = re.sub(
            r"^provides=.+$", "provides=('intel-xpu-smi')", content, flags=re.MULTILINE
        )
        content = re.sub(
            r"^depends=\(.*?^\)",
            "depends=(\n"
            "    'intel-compute-runtime'\n"
            "    'level-zero-loader'\n"
            "    'igsc>=1.3.1'\n"
            "    'hwloc'\n"
            "    'libpciaccess'\n"
            ")",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
    content = re.sub(
        r"^sha256sums=.+$", "sha256sums=('SKIP')", content, flags=re.MULTILINE
    )
    pkgbuild.write_text(content)
    return True


def write_output(updated_packages):
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as stream:
            stream.write(f"updated={str(bool(updated_packages)).lower()}\n")
            stream.write(f"packages={' '.join(updated_packages)}\n")
    else:
        print(f"Updated packages: {' '.join(updated_packages) or 'none'}")


def main():
    try:
        releases = get_latest_info()
        updated = []
        for package, (version, build) in releases.items():
            if package == "intel-xpu-smi-bin" and not Path(
                "/usr/lib/libigsc.so.1"
            ).exists():
                print("Skipping XPU-SMI 2.x: Arch does not provide libigsc.so.1 yet.")
                continue
            if update_pkgbuild(package, version, build):
                updated.append(package)
        write_output(updated)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
