from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, RequestFactory

from intelligence.models import User, Role
from .models import ACMLink
from .components_history import persist_component_history
from .valuation_metrics import valuation_comparison, history_comparison, adjustment_kpis
from .views import historial_acm
from .test_components import params, sample
from .components_engine import candidates, calculate, parameters


class ValuationMetricsTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name='agent')
        self.user = User.objects.create(username='agent', phone='900000001', role=self.role)

    def test_formula_direction_zero_and_non_finite_values(self):
        for agent, pct in ((220000, 10), (180000, -10), (200000, 0), (0, -100)):
            comparison = valuation_comparison({'manual_valuation': agent}, {'new': {'total': 200000}})
            self.assertEqual(comparison['variation_pct'], pct)
            self.assertEqual(comparison['absolute_variation_pct'], abs(pct))
        for agent in (None, 'nan', 'inf', -1):
            self.assertIsNone(valuation_comparison({'manual_valuation': agent}, {'new': {'total': 200000}})['variation_pct'])
        self.assertIsNone(valuation_comparison({'manual_valuation': 100}, {'new': {'total': 0}})['variation_pct'])

    def test_saved_adjustment_retains_original_and_deduplicates_download(self):
        p = parameters(params()); rows = candidates(sample(), p); result = calculate(rows, p)
        base = result['new']['total']; p['manual_valuation'] = round(base * 1.1, 2)
        saved, created = persist_component_history(self.user, p, rows, result)
        saved.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual(saved.resultado_json['new']['total'], base)
        comparison = saved.resultado_json['valuation_comparison']
        self.assertAlmostEqual(comparison['variation_pct'], 10, places=3)
        self.assertEqual(saved.valor_comercial, Decimal(str(p['manual_valuation'])))
        self.assertEqual(saved.user, self.user)
        again, created = persist_component_history(self.user, p, rows, result)
        self.assertFalse(created); self.assertEqual(saved.pk, again.pk)
        self.assertEqual(ACMLink.objects.count(), 1)
        p.pop('manual_valuation')
        restored, _ = persist_component_history(self.user, p, rows, result)
        self.assertIsNone(history_comparison(restored)['agent_total'])

    def test_absolute_mean_does_not_cancel_opposite_adjustments_or_include_unreviewed(self):
        result = {'new': {'total': 200000}}
        comparisons = [valuation_comparison(p, result) for p in
                       ({'manual_valuation': 220000}, {'manual_valuation': 180000}, {})]
        comparisons.append(valuation_comparison({'manual_valuation': 10}, {'new': {'total': 0}}))
        kpis = adjustment_kpis(comparisons)
        self.assertEqual(kpis['mean_absolute_variation'], 10)
        self.assertEqual(kpis['mean_signed_variation'], 0)
        self.assertEqual(kpis['reviewed_count'], 2)
        self.assertEqual(kpis['within_ten_pct'], 100)
        self.assertIsNone(adjustment_kpis([])['mean_absolute_variation'])

    def test_old_history_derives_metrics_without_fabricating_review(self):
        history = SimpleNamespace(metodo='componentes', parametros_json={'manual_valuation': 240000},
                                  resultado_json={'new': {'total': 200000}})
        self.assertEqual(history_comparison(history)['variation_pct'], 20)
        history.parametros_json = {}
        self.assertIsNone(history_comparison(history)['agent_total'])
        history.metodo = 'clasico'
        self.assertIsNone(history_comparison(history)['calculated_total'])

    def test_history_is_scoped_to_agent_and_renders_kpis(self):
        p = parameters(params()); rows = candidates(sample(), p); result = calculate(rows, p)
        p['manual_valuation'] = round(result['new']['total'] * 1.1, 2)
        saved, _ = persist_component_history(self.user, p, rows, result)
        other = User.objects.create(username='other', phone='900000002', role=self.role)
        persist_component_history(other, {**p, 'manual_valuation': 1}, rows, result)
        request = RequestFactory().get('/acm/historial/'); request.current_user = self.user
        with patch('acm.views.render', wraps=__import__('django.shortcuts', fromlist=['render']).render) as render:
            response = historial_acm(request)
        context = render.call_args.args[2]
        self.assertEqual(context['adjustment_kpis']['reviewed_count'], 1)
        self.assertEqual([item.pk for item in context['acms']], [saved.pk])
        self.assertContains(response, 'Valor ACM calculado')
        self.assertContains(response, 'Valor del agente')
        self.assertContains(response, 'Variación absoluta media')
        self.assertRegex(response.content.decode(), r'\+10%')
