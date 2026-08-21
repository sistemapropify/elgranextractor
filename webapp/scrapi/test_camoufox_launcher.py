import json
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

    def test_waits_for_background_dependency_installation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "camoufox-deps.installing"
            marker.touch()

            def finish_install(_seconds):
                marker.unlink()

            with (
                patch.object(launcher, "is_headless_server", return_value=True),
                patch.object(launcher, "_CAMOUFOX_DEPS_INSTALLING", marker),
                patch.object(
                    launcher,
                    "_missing_camoufox_dependencies",
                    side_effect=[["libgtk-3.so.0"], []],
                ),
                patch.object(launcher.time, "sleep", side_effect=finish_install),
            ):
                launcher.ensure_camoufox_system_dependencies()
    def test_dead_install_owner_is_replaced_without_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / 'camoufox'
            lock = install_dir / '.propifai-fetch.lock'
            browser = install_dir / 'browsers' / 'official' / 'stable'
            lock.mkdir(parents=True)
            (lock / 'owner.json').write_text(
                json.dumps({'pid': 999999, 'boot_id': 'same-boot'}),
                encoding='utf-8',
            )
            browser.mkdir(parents=True)
            pkgman = types.ModuleType('camoufox.pkgman')
            pkgman.camoufox_path = lambda download_if_missing=True: browser

            with (
                patch.object(
                    launcher, '_installed_path', side_effect=[None, None, None]
                ),
                patch.object(launcher, 'get_install_dir', return_value=install_dir),
                patch.object(launcher, '_boot_id', return_value='same-boot'),
                patch.object(launcher.os, 'kill', side_effect=OSError),
                patch.object(launcher.time, 'sleep') as sleep,
                patch.dict(sys.modules, {'camoufox.pkgman': pkgman}),
            ):
                self.assertEqual(launcher.ensure_camoufox_installed(), browser)

            sleep.assert_not_called()
            self.assertFalse(lock.exists())
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
