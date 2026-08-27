from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class UnifiedNavigationTests(SimpleTestCase):
    """Evita que reaparezcan layouts o dependencias visuales paralelas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_dir = Path(settings.BASE_DIR)
        cls.shell = (cls.base_dir / "templates" / "propifai_base.html").read_text(
            encoding="utf-8"
        )

    def template_sources(self):
        roots = [self.base_dir / "templates"]
        roots.extend(path for path in self.base_dir.glob("*/templates") if path.is_dir())
        for root in roots:
            yield from root.rglob("*.html")

    def test_only_the_shared_shell_declares_the_global_sidebar(self):
        declarations = []
        for template in self.template_sources():
            if any(part in {"venv", "staticfiles"} for part in template.parts):
                continue
            content = template.read_text(encoding="utf-8", errors="ignore")
            if '<nav class="app-sidebar"' in content:
                declarations.append(template.relative_to(self.base_dir).as_posix())
        self.assertEqual(declarations, ["templates/propifai_base.html"])

    def test_menu_keeps_the_business_sections(self):
        expected = (
            "Gesti&oacute;n Inmobiliaria",
            "An&aacute;lisis & Mercado",
            "Marketing & Prospecci&oacute;n",
            "Inteligencia Artificial",
            "Administraci&oacute;n IA",
            "Monitoreo",
            "Sistema",
        )
        for section in expected:
            with self.subTest(section=section):
                self.assertIn(section, self.shell)

    def test_bootstrap_runtime_is_not_loaded(self):
        forbidden = (
            "cdn.jsdelivr.net/npm/bootstrap",
            "bootstrap-icons",
            "bootstrap.bundle",
        )
        violations = []
        sources = list(self.template_sources())
        sources.extend((self.base_dir / "static").rglob("*.css"))
        sources.extend((self.base_dir / "static").rglob("*.js"))
        for source in sources:
                if any(part in {"venv", "staticfiles"} for part in source.parts):
                    continue
                content = source.read_text(encoding="utf-8", errors="ignore").lower()
                if any(token in content for token in forbidden):
                    violations.append(source.relative_to(self.base_dir).as_posix())
        self.assertEqual(violations, [])

    def test_legacy_base_delegates_to_the_shared_shell(self):
        legacy_base = (self.base_dir / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('{% extends "propifai_base.html" %}', legacy_base)
        self.assertNotIn("<nav", legacy_base)

    def test_lead_dashboard_javascript_is_not_rendered_as_text(self):
        dashboard = (
            self.base_dir
            / "lead_intelligence"
            / "templates"
            / "lead_intelligence"
            / "overview_dashboard.html"
        ).read_text(encoding="utf-8")
        extra_js = dashboard.split("{% block extra_js %}", 1)[1]
        self.assertIn("<script>", extra_js)
        self.assertIn("</script>", extra_js)
        self.assertLess(extra_js.index("<script>"), extra_js.index("const element"))
        self.assertGreater(extra_js.index("</script>"), extra_js.index("const element"))

    def test_lead_intelligence_uses_the_dark_palette(self):
        styles = (
            self.base_dir
            / "lead_intelligence"
            / "templates"
            / "lead_intelligence"
            / "_dashboard_styles.html"
        ).read_text(encoding="utf-8")
        for token in ("#0d1117", "#161b22", "#30363d", "#c9d1d9", "#58a6ff"):
            with self.subTest(token=token):
                self.assertIn(token, styles)
