"""
Management command para generar un Excel con todos los campos de la tabla properties
de la base de datos Propifai, incluyendo relaciones, indices y nombres legibles.

Uso: python manage.py generar_excel_campos_propifai
"""

import os
import sys
from django.core.management.base import BaseCommand
from django.db import connections
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class Command(BaseCommand):
    help = 'Genera un Excel con todos los campos de properties y sus relaciones'

    def handle(self, *args, **options):
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path