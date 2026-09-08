"""Explicit test labels avoid duplicate imports through the webapp package."""
import os
import sys
from pathlib import Path

from django.core.management import execute_from_command_line


def test_labels():
    root = Path(__file__).resolve().parent
    labels = []
    for module in ('lead_intelligence', 'prospects', 'response_intelligence'):
        labels.extend(f'{module}.{path.stem}' for path in sorted((root / module).glob('test*.py')))
    labels.extend(f'n8n_bridge.tests.{path.stem}'
                  for path in sorted((root / 'n8n_bridge/tests').glob('test*.py')))
    labels.extend(f'intelligence.tests.{path.stem}'
                  for path in sorted((root / 'intelligence/tests').glob('test_semantic*.py')))
    labels += ['intelligence.tests.test_reasoning_contracts',
               'intelligence.tests.test_chat_web_conversations']
    return labels


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'integration_test_settings')
    execute_from_command_line([sys.argv[0], 'test', *test_labels(), '--noinput', *sys.argv[1:]])
