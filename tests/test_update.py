import tempfile
import unittest
from pathlib import Path

from scripts.update import (
    IGSC_TAG_PATTERN,
    THINKWATCH_TAG_PATTERN,
    bump_version,
    parse_release_tag,
    parse_xpu_asset,
    pick_thinkwatch_asset,
    update_deb_pkgbuild,
    update_source_pkgbuild,
    update_thinkwatch_pkgbuild,
)


class UpdateTest(unittest.TestCase):
    def test_v2_asset_and_pkgbuild_migration(self):
        self.assertEqual(
            parse_xpu_asset("xpu-smi_2.0.1-1.24.04_amd64.deb"),
            ("intel-xpu-smi-bin", "2.0.1", "1.24.04"),
        )
        self.assertEqual(
            parse_xpu_asset(
                "xpumanager_1.3.7_20260530.031049.9fc2535d.u24.04_amd64.deb"
            ),
            (
                "intel-xpumanager-bin",
                "1.3.7",
                "20260530.031049.9fc2535d.u24.04",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "intel-xpu-smi-bin"
            package.mkdir()
            pkgbuild = package / "PKGBUILD"
            pkgbuild.write_text(
                "pkgver=1.3.7\npkgrel=1\n_buildver=old.u24.04\n"
                "depends=(\n    'igsc'\n)\n"
                "provides=('intel-xpu-smi' 'libxpum.so')\n"
                'source=("xpu-smi_${pkgver}_${_buildver}_amd64.deb")\n'
                "sha256sums=('old')\n"
                'bsdtar -O -xf "$source" data.tar.gz\n'
            )

            self.assertTrue(update_deb_pkgbuild(package, "2.0.1", "1.24.04"))
            content = pkgbuild.read_text()
            self.assertIn("xpu-smi_${pkgver}-${_buildver}_amd64.deb", content)
            self.assertIn("data.tar.zst", content)
            self.assertIn("provides=('intel-xpu-smi')", content)
            self.assertIn("'igsc>=1.3.1'", content)
            self.assertIn("'intel-metee'", content)
            self.assertIn("'hwloc'", content)
            self.assertFalse(update_deb_pkgbuild(package, "2.0.1", "1.24.04"))

    def test_igsc_release_tag(self):
        self.assertEqual(parse_release_tag("V1.3.2", IGSC_TAG_PATTERN), "1.3.2")
        self.assertIsNone(parse_release_tag("v1.3.2", IGSC_TAG_PATTERN))
        self.assertIsNone(parse_release_tag("1.3.2", IGSC_TAG_PATTERN))
        self.assertIsNone(parse_release_tag("V1.3.2-rc1", IGSC_TAG_PATTERN))

    def test_thinkwatch_release_tag(self):
        self.assertEqual(
            parse_release_tag("v2026.10.1", THINKWATCH_TAG_PATTERN), "2026.10.1"
        )
        self.assertIsNone(parse_release_tag("2026.10.1", THINKWATCH_TAG_PATTERN))
        self.assertIsNone(parse_release_tag("V2026.10.1", THINKWATCH_TAG_PATTERN))
        self.assertIsNone(
            parse_release_tag("v2026.10.1-beta", THINKWATCH_TAG_PATTERN)
        )

    def test_thinkwatch_asset_is_taken_from_the_release(self):
        # The name lost the `linux-` prefix in 2026.10.2; both are the package's
        # source, and a release whose AppImage is not uploaded yet has neither
        self.assertEqual(
            pick_thinkwatch_asset(
                {"assets": [{"name": "ThinkWatch-Lite-2026.10.1-x86_64.AppImage"}]}
            ),
            "ThinkWatch-Lite-2026.10.1-x86_64.AppImage",
        )
        self.assertEqual(
            pick_thinkwatch_asset(
                {
                    "assets": [
                        {"name": "ThinkWatch-Lite-2026.10.2-linux-x86_64.AppImage"},
                        {
                            "name": "ThinkWatch-Lite-2026.10.2-linux-aarch64.AppImage"
                        },
                        {
                            "name": "ThinkWatch-Lite-2026.10.2-linux-x86_64.AppImage.sha256"
                        },
                    ]
                }
            ),
            "ThinkWatch-Lite-2026.10.2-linux-x86_64.AppImage",
        )
        self.assertIsNone(pick_thinkwatch_asset({"assets": [{"name": "install.sh"}]}))
        self.assertIsNone(pick_thinkwatch_asset({}))

    def test_igsc_pkgbuild_keeps_build_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "intel-igsc"
            package.mkdir()
            pkgbuild = package / "PKGBUILD"
            pkgbuild.write_text(
                "pkgver=1.3.1\n"
                "pkgrel=2\n"
                "source=(\"igsc-$pkgver.tar.gz::https://example.invalid/V$pkgver.tar.gz\")\n"
                "sha256sums=('deadbeef')\n"
            )

            self.assertTrue(update_source_pkgbuild(package, "1.3.2"))
            content = pkgbuild.read_text()
            self.assertIn("pkgver=1.3.2", content)
            self.assertIn("pkgrel=1", content)
            self.assertIn("sha256sums=('SKIP')", content)
            self.assertIn('V$pkgver.tar.gz', content)
            self.assertFalse(update_source_pkgbuild(package, "1.3.2"))

    def test_thinkwatch_pkgbuild_takes_the_asset_name_from_the_release(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "thinkwatch-lite-bin"
            package.mkdir()
            pkgbuild = package / "PKGBUILD"
            pkgbuild.write_text(
                "pkgver=2026.10.1\n"
                "pkgrel=2\n"
                '_asset="ThinkWatch-Lite-$pkgver-x86_64.AppImage"\n'
                'source=("$_asset::https://example.invalid/v$pkgver/$_asset"\n'
                '        "LICENSE::https://example.invalid/v$pkgver/LICENSE")\n'
                "sha256sums=('aa'\n            'bb')\n"
                "build() {\n"
                '  chmod +x "$_asset"\n'
                '  ./"$_asset" --appimage-extract\n'
                "}\n"
            )

            self.assertTrue(
                update_thinkwatch_pkgbuild(
                    package, "2026.10.2", "ThinkWatch-Lite-2026.10.2-linux-x86_64.AppImage"
                )
            )
            content = pkgbuild.read_text()
            self.assertIn("pkgver=2026.10.2", content)
            self.assertIn("pkgrel=1", content)
            self.assertIn("sha256sums=('SKIP')", content)
            self.assertIn(
                '_asset="ThinkWatch-Lite-$pkgver-linux-x86_64.AppImage"', content
            )
            self.assertNotIn("'aa'", content)
            # The build recipe itself is left alone
            self.assertIn('chmod +x "$_asset"', content)
            self.assertFalse(
                update_thinkwatch_pkgbuild(
                    package, "2026.10.2", "ThinkWatch-Lite-2026.10.2-linux-x86_64.AppImage"
                )
            )

    def test_wrapped_checksums_are_replaced_as_a_whole(self):
        self.assertEqual(
            bump_version(
                "pkgver=2026.10.1\npkgrel=3\n"
                "sha256sums=('aa'\n            'bb')\n",
                "2026.11.1",
            ),
            "pkgver=2026.11.1\npkgrel=1\nsha256sums=('SKIP')\n",
        )


if __name__ == "__main__":
    unittest.main()
