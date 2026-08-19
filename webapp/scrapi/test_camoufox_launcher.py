import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapi import camoufox_launcher as launcher


class CamoufoxLauncherTests(unittest.TestCase):
    def test_kwargs_do_not_pass_unsupported_data_dir(self):
        with patch.object(launcher, "ensure_camoufox_installed"):
            options = launcher.camoufox_kwargs(headless=True)

        self.assertTrue(options["headless"])
        self.assertNotIn("data_dir", options)

    def test_kwargs_validate_system_dependencies(self):
        with (
            patch.object(launcher, 'ensure_camoufox_installed'),
            patch.object(launcher, 'ensure_camoufox_system_dependencies') as check,
        ):
            launcher.camoufox_kwargs(headless=True)

        check.assert_called_once_with()

    def test_missing_linux_library_fails_before_browser_launch(self):
        with (
            patch.object(launcher, 'is_headless_server', return_value=True),
            patch.object(launcher.ctypes, 'CDLL', side_effect=OSError),
        ):
            with self.assertRaises(launcher.CamoufoxSystemDependencyError):
                launcher.ensure_camoufox_system_dependencies()

    def test_existing_browser_skips_download(self):
        browser = Path("/tmp/camoufox/browser")
        with patch.object(launcher, "_installed_path", return_value=browser):
            self.assertEqual(launcher.ensure_camoufox_installed(), browser)

    def test_missing_browser_uses_native_auto_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "camoufox"
            browser = install_dir / "browsers" / "official" / "stable"
            browser.mkdir(parents=True)
            pkgman = types.ModuleType("camoufox.pkgman")
            pkgman.camoufox_path = lambda download_if_missing=True: browser

            with (
                patch.object(launcher, "_installed_path", side_effect=[None, None]),
                patch.object(launcher, "get_install_dir", return_value=install_dir),
                patch.dict(sys.modules, {"camoufox.pkgman": pkgman}),
            ):
                self.assertEqual(launcher.ensure_camoufox_installed(), browser)


if __name__ == "__main__":
    unittest.main()
