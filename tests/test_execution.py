"""Portable entry-point checks; all reporting inputs are synthetic."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import analyze_meta, review_pack
from tests.test_analysis_views import drivers

REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPTS = REPOSITORY / 'scripts'


class ExecutionTests(unittest.TestCase):
    def test_absolute_path_commands_work_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / 'synthetic-input.json'
            payload = drivers()
            payload['rows'][0]['name'] = 'Café 東京'
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            commands = [
                ('analyze_meta.py', []),
                ('review_pack.py', []),
                ('analysis_views.py', ['--view', 'compact']),
                ('analysis_views.py', ['--view', 'focus', '--fields', 'metrics.spend,derived_metrics.cpm']),
                ('analysis_views.py', ['--view', 'drivers']),
            ]
            for script, arguments in commands:
                with self.subTest(script=script, arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS / script), str(input_path), *arguments],
                        cwd=root, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout)
                    self.assertIn('Café 東京', result.stdout)
                    if arguments and arguments[-1] == 'drivers':
                        self.assertEqual(output['status'], 'computed')
                        self.assertEqual(output['source_input']['path'], str(input_path.resolve()))
            self.assertEqual([path.name for path in root.iterdir()], ['synthetic-input.json'])

    def test_package_entry_points_and_compatibility_alias(self):
        self.assertIs(review_pack.analyze, analyze_meta.analyze)
        for module in ('scripts.analyze_meta', 'scripts.analysis_views', 'scripts.review_pack'):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, '-m', module, '--help'],
                    cwd=REPOSITORY, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_source_uses_python_310_syntax(self):
        # A grammar check supplements (but does not replace) CI on Python 3.10.
        for directory in (SCRIPTS, REPOSITORY / 'tests'):
            for path in directory.glob('*.py'):
                with self.subTest(path=path.name):
                    ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 10))


if __name__ == '__main__':
    unittest.main()
