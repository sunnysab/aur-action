import json
import os
import re
import sys
import time
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


XPU_RELEASES_API = "https://api.github.com/repos/intel/xpumanager/releases?per_page=20"
IGSC_RELEASES_API = "https://api.github.com/repos/intel/igsc/releases?per_page=20"

# Packages whose PKGBUILD is driven by a .deb asset of an upstream release.
XPU_ASSET_PATTERNS = {
    "intel-xpumanager-bin": re.compile(
        r"^xpumanager_(?P<version>\d+(?:\.\d+)+)_(?P<build>[^_]+)_amd64\.deb$"
    ),
    "intel-xpu-smi-bin": re.compile(
        r"^xpu-smi_(?P<version>\d+(?:\.\d+)+)-(?P<build>[^_]+)_amd64\.deb$"
    ),
}

# Package built from the upstream source tarball of a release tag (V1.3.2).
IGSC_PACKAGE = "intel-igsc"
IGSC_TAG_PATTERN = re.compile(r"^V(?P<version>\d+(?:\.\d+)+)$")


def fetch_releases(api):
    print(f"Fetching {api}")
    request = Request(api, headers={"User-Agent": "aur-action"})
    # The xpumanager release list is a few hundred KB and GitHub occasionally
    # drops the connection halfway through; retry a couple of times.
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except (IncompleteRead, URLError, TimeoutError) as error:
            if attempt == 2:
                raise
            print(f"Retrying after {error}")
            time.sleep(attempt + 1)


def parse_xpu_asset(name):
    for package, pattern in XPU_ASSET_PATTERNS.items():
        if match := pattern.fullmatch(name):
            return package, *match.group("version", "build")
    return None


def parse_igsc_tag(tag):
    match = IGSC_TAG_PATTERN.fullmatch(tag)
    return match.group("version") if match else None


def get_xpu_releases():
    """Latest Ubuntu 24.04 .deb of every XPU package, keyed by AUR package name."""
    found = {}
    for release in fetch_releases(XPU_RELEASES_API):
        for asset in release.get("assets", []):
            parsed = parse_xpu_asset(asset["name"])
            if parsed and parsed[2].endswith("24.04"):
                found.setdefault(parsed[0], parsed[1:])
        if len(found) == len(XPU_ASSET_PATTERNS):
            break

    missing = XPU_ASSET_PATTERNS.keys() - found.keys()
    if missing:
        raise RuntimeError(f"No Ubuntu 24.04 asset found for: {', '.join(missing)}")
    return found


def get_igsc_version():
    for release in fetch_releases(IGSC_RELEASES_API):
        if release.get("prerelease") or release.get("draft"):
            continue
        if version := parse_igsc_tag(release.get("tag_name", "")):
            return version
    raise RuntimeError("No stable igsc release tag matching V<version> found")


def read_pkgbuild(pkg_path):
    path = Path(pkg_path) / "PKGBUILD"
    content = path.read_text()

    def field(name):
        match = re.search(rf"^{name}=(\S+)", content, re.MULTILINE)
        return match.group(1) if match else None

    return path, content, field("pkgver"), field("_buildver")


def bump_version(content, version):
    content = re.sub(r"^pkgver=.+$", f"pkgver={version}", content, flags=re.MULTILINE)
    content = re.sub(r"^pkgrel=.+$", "pkgrel=1", content, flags=re.MULTILINE)
    # The CI runs updpkgsums afterwards, which fills in the real checksums.
    return re.sub(
        r"^sha256sums=.+$", "sha256sums=('SKIP')", content, flags=re.MULTILINE
    )


def update_deb_pkgbuild(pkg_path, version, build):
    path, content, current_version, current_build = read_pkgbuild(pkg_path)
    if (current_version, current_build) == (version, build):
        print(f"[{pkg_path}] Already up to date ({version}-{build}).")
        return False

    print(f"[{pkg_path}] Updating to {version}-{build}")
    content = bump_version(content, version)
    content = re.sub(
        r"^_buildver=.+$", f"_buildver={build}", content, flags=re.MULTILINE
    )
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
        # 2.x links against libigsc.so.1, which only igsc >= 1.3.1 provides,
        # and against libmetee directly (relinked in package()).
        content = re.sub(
            r"^depends=\(.*?^\)",
            "depends=(\n"
            "    'intel-compute-runtime'\n"
            "    'level-zero-loader'\n"
            "    'igsc>=1.3.1'\n"
            "    'intel-metee'\n"
            "    'hwloc'\n"
            "    'libpciaccess'\n"
            ")",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
    path.write_text(content)
    return True


def update_source_pkgbuild(pkg_path, version):
    path, content, current_version, _ = read_pkgbuild(pkg_path)
    if current_version == version:
        print(f"[{pkg_path}] Already up to date ({version}).")
        return False

    print(f"[{pkg_path}] Updating to {version}")
    path.write_text(bump_version(content, version))
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
        updated = []
        for package, (version, build) in get_xpu_releases().items():
            if update_deb_pkgbuild(package, version, build):
                updated.append(package)
        if update_source_pkgbuild(IGSC_PACKAGE, get_igsc_version()):
            updated.append(IGSC_PACKAGE)
        write_output(updated)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
