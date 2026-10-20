"""The cadastral facade comparison is included in the basic ACM."""
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from .access import DEFAULTS

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [Path(__file__).parent / 'templates'],
    'OPTIONS': {'loaders': [
        ('django.template.loaders.locmem.Loader', {'propifai_base.html':
            '<html><head>{% block extra_head %}{% endblock %}</head>'
            '<body>{% block content %}{% endblock %}{% block extra_scripts %}{% endblock %}</body></html>'}),
        'django.template.loaders.filesystem.Loader',
    ]},
}]


@override_settings(TEMPLATES=TEMPLATES)
class CadastralFacadeTemplateTests(SimpleTestCase):
    def render(self, **permissions):
        return render_to_string('acm/components.html', {
            'acm_permissions': {**DEFAULTS, **permissions},
        })

    def test_basic_role_receives_both_facades_without_street_view_tool_permission(self):
        html = self.render(cadastral_info=True, street_view=False)
        self.assertIn('id="cmp-cadastral-photo"', html)
        self.assertIn('id="cmp-street-preview"', html)
        self.assertLess(html.index('id="cmp-cadastral-photo"'), html.index('id="cmp-street-preview"'))
        self.assertIn('/static/js/street-facade-view.js?v=1', html)
        self.assertIn('/static/acm/js/street-facade.js?v=3', html)

    def test_disabling_the_cadastral_card_removes_both_facades_and_their_scripts(self):
        html = self.render(cadastral_info=False, street_view=True)
        self.assertNotIn('id="cmp-cadastral-photo"', html)
        self.assertNotIn('id="cmp-street-preview"', html)
        self.assertNotIn('/static/js/street-facade-view.js', html)
        self.assertNotIn('/static/acm/js/street-facade.js', html)

    def test_basic_role_can_open_cadastral_pdf_without_analysis_reports_permission(self):
        html = self.render(reports=False)
        self.assertIn('id="cmp-cadastral-pdf"', html)
        self.assertIn('Abrir reporte PDF', html)

    def test_explicit_cadastral_pdf_restriction_hides_link_only(self):
        html = self.render(cadastral_pdf=False)
        self.assertIn('id="cmp-cadastral-fields"', html)
        self.assertNotIn('id="cmp-cadastral-pdf"', html)
