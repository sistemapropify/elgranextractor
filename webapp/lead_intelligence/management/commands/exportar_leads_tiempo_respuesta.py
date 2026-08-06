"""Exporta a Excel los leads entrantes de los últimos N días con el tiempo
(minutos) que el agente tarda en responder por primera vez al lead.

La métrica clave corresponde a la primera etapa del embudo ("Contactados"):
tiempo desde la primera pregunta del lead (first_lead_at) hasta la primera
respuesta del agente (first_agent_response_at).
"""

from datetime import timedelta

import pandas as pd

from django.core.management.base import BaseCommand
from django.utils import timezone

from lead_intelligence.conversation_analysis import LIMA_TIMEZONE, analyze_chat_history
from lead_intelligence.services import _lead_result_rows


def _fmt(value):
    if value is None:
        return None
    return value.astimezone(LIMA_TIMEZONE).strftime("%d/%m/%Y %H:%M")


class Command(BaseCommand):
    help = (
        "Exporta a Excel los leads entrantes de los últimos N días con el tiempo "
        "(minutos) de la primera respuesta del agente (embudo 'Contactados')."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--output", default="leads_tiempo_respuesta.xlsx")

    def handle(self, *args, **options):
        days = max(1, options["days"])
        date_to = timezone.localdate()
        date_from = date_to - timedelta(days=days - 1)
        rows = _lead_result_rows(date_from, date_to)

        records = []
        for row in rows:
            analysis = analyze_chat_history(row["chat_history"])
            seconds = analysis.get("first_response_seconds")
            minutes = round(seconds / 60, 1) if seconds is not None else None
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            business_name = (row.get("business_name") or "").strip()
            display_name = (
                f"{first_name} {last_name}".strip()
                or business_name
                or f"Lead #{row['id']}"
            )
            records.append(
                {
                    "Lead ID": row["id"],
                    "Nombre": display_name,
                    "Agente asignado": row.get("agent_name") or "Sin asignar",
                    "Fuente": row.get("source") or "",
                    "Canal": row.get("channel_name") or "",
                    "Estado": row.get("status_name") or "",
                    "Fecha ingreso": _fmt(row.get("entered_at")),
                    "Primera pregunta del lead": _fmt(
                        analysis.get("first_lead_at")
                    ),
                    "Primera respuesta del agente": _fmt(
                        analysis.get("first_agent_response_at")
                    ),
                    "Tiempo 1ra respuesta (min)": minutes,
                    "Contactado": "Sí"
                    if analysis.get("contacted")
                    else "No",
                }
            )

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.sort_values("Fecha ingreso").reset_index(drop=True)

        contacted = df[df["Contactado"] == "Sí"] if not df.empty else df
        tiempos = pd.to_numeric(
            contacted["Tiempo 1ra respuesta (min)"], errors="coerce"
        ).dropna()

        summary = pd.DataFrame(
            {
                "Métrica": [
                    "Periodo",
                    "Leads entrantes",
                    "Contactados (1ra etapa)",
                    "% contactados",
                    "Sin primera respuesta",
                    "Promedio 1ra respuesta (min)",
                    "Mediana 1ra respuesta (min)",
                    "Mínimo (min)",
                    "Máximo (min)",
                ],
                "Valor": [
                    f"{date_from} → {date_to}",
                    len(df),
                    len(contacted),
                    f"{round(len(contacted) / len(df) * 100, 1) if len(df) else 0}%",
                    len(df) - len(contacted),
                    round(tiempos.mean(), 1) if not tiempos.empty else None,
                    round(tiempos.median(), 1) if not tiempos.empty else None,
                    round(tiempos.min(), 1) if not tiempos.empty else None,
                    round(tiempos.max(), 1) if not tiempos.empty else None,
                ],
            }
        )

        output = options["output"]
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Resumen", index=False)
            df.to_excel(
                writer,
                sheet_name="Leads",
                index=False,
                startrow=0,
            )
            # Autofiltro y ancho de columnas en la hoja de leads.
            ws = writer.sheets["Leads"]
            ws.auto_filter.ref = ws.dimensions
            for idx, col in enumerate(df.columns, start=1):
                col_len = max(
                    df[col].astype(str).str.len().max()
                    if not df.empty
                    else 0,
                    len(str(col)),
                )
                ws.column_dimensions[
                    ws.cell(row=1, column=idx).column_letter
                ].width = min(max(col_len + 2, 10), 32)

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: {len(df)} leads ({date_from} → {date_to}) exportados a "
                f"{output}. Contactados: {len(contacted)}; "
                f"tiempo promedio 1ra respuesta: "
                f"{round(tiempos.mean(), 1) if not tiempos.empty else 'n/d'} min."
            )
        )
