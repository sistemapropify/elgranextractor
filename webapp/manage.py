#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
