"""SPEC Fase 2 — Corre el eval set de enrutamiento contra find_best_skill actual.

Uso:
    python manage.py run_skill_evals --notes "baseline"
    python manage.py run_skill_evals --notes "post cambio desc busqueda_exacta"
"""

from django.core.management.base import BaseCommand

from intelligence.models import SkillEvalCase, SkillEvalResult, SkillEvalRun
from intelligence.skills.registry import SkillRegistry


class Command(BaseCommand):
    help = "Corre el eval set de enrutamiento contra find_best_skill actual"

    def add_arguments(self, parser):
        parser.add_argument("--notes", type=str, default="")

    def handle(self, *args, **options):
        registry = SkillRegistry()
        cases = SkillEvalCase.objects.filter(active=True)
        run = SkillEvalRun.objects.create(
            total_cases=cases.count(),
            correct=0,
            accuracy=0.0,
            threshold_used=registry.get_router_threshold(),
            notes=options["notes"],
        )
        correct = 0
        for case in cases:
            skill, score = registry.find_best_skill(case.query, return_score=True)
            predicted = skill.name if skill else "NINGUNA"
            is_correct = predicted == case.expected_skill
            correct += int(is_correct)
            SkillEvalResult.objects.create(
                run=run,
                case=case,
                predicted_skill=predicted,
                is_correct=is_correct,
                similarity_score=score,
            )
        run.correct = correct
        run.accuracy = correct / run.total_cases if run.total_cases else 0
        run.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Accuracy: {run.accuracy:.2%} "
                f"({correct}/{run.total_cases}) · threshold={run.threshold_used}"
            )
        )
