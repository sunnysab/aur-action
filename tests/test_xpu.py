import tempfile
import unittest
from pathlib import Path

from scripts.xpu import parse_asset, update_pkgbuild


class XpuTest(unittest.TestCase):
    def test_v2_asset_and_pkgbuild_migration(self):
        self.assertEqual(
            parse_asset("xpu-smi_2.0.1-1.24.04_amd64.deb"),
            ("intel-xpu-smi-bin", "2.0.1", "1.24.04"),
        )
        self.assertEqual(
            parse_asset(
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

            self.assertTrue(update_pkgbuild(package, "2.0.1", "1.24.04"))
            content = pkgbuild.read_text()
            self.assertIn("xpu-smi_${pkgver}-${_buildver}_amd64.deb", content)
            self.assertIn("data.tar.zst", content)
            self.assertIn("provides=('intel-xpu-smi')", content)
            self.assertIn("'igsc>=1.3.1'", content)
            self.assertIn("'hwloc'", content)


if __name__ == "__main__":
    unittest.main()
