import json
from datetime import datetime, timezone

from django.template.loader import get_template
from django.test import SimpleTestCase

from .remarketing import detect_remarketing_launches, is_remarketing_message


TEMPLATE = (
    "Hola de nuevo 👋 Si te sigue interesando la propiedad, puedo coordinarte "
    "una visita. O si prefieres, dime qué estás buscando y te muestro otras opciones."
)


def message(sender, text, hour, message_id):
    return {
        "id": message_id,
        "sender": sender,
        "text": text,
        "timestamp": datetime(2026, 8, 1, hour, tzinfo=timezone.utc).isoformat(),
    }


class RemarketingDetectionTests(SimpleTestCase):
    def test_only_validated_template_is_recognized(self):
        self.assertTrue(is_remarketing_message(TEMPLATE))
        self.assertFalse(
            is_remarketing_message(
                "¿Pudiste leer mi mensaje? Coméntame qué más deseas saber."
            )
        )

    def test_reply_is_attributed_to_launch(self):
        history = json.dumps(
            [
                message("lead", "Quiero información", 8, "1"),
                message("agent", "Te envié los datos", 9, "2"),
                message("bot", TEMPLATE, 10, "3"),
                message("lead", "Sí, quiero visitarla", 11, "4"),
            ]
        )

        launches = detect_remarketing_launches(history)

        self.assertEqual(len(launches), 1)
        self.assertIsNotNone(launches[0]["response_at"])
        self.assertEqual(launches[0]["response_seconds"], 3600)
        self.assertEqual(launches[0]["sender"], "bot")

    def test_one_reply_does_not_credit_two_launches(self):
        history = json.dumps(
            [
                message("agent", "Información inicial", 8, "1"),
                message("bot", TEMPLATE, 9, "2"),
                message("bot", TEMPLATE, 10, "3"),
                message("lead", "Ahora sí, coordinemos", 11, "4"),
            ]
        )

        launches = detect_remarketing_launches(history)

        self.assertEqual(len(launches), 2)
        self.assertIsNone(launches[0]["response_at"])
        self.assertIsNotNone(launches[1]["response_at"])

    def test_dashboard_template_compiles(self):
        self.assertIsNotNone(
            get_template("lead_intelligence/remarketing_dashboard.html")
        )
