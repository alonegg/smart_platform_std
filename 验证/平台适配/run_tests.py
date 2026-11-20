"""Run all WP4a offline suites in isolated interpreters, without containers."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUITES = (
    ('package', ROOT, 'test_package.py'),
    ('moodle', ROOT / 'moodle', 'test_*.py'),
    ('openedx', ROOT / 'openedx', 'test_*.py'),
)


def run_suites(suites=SUITES):
    if not suites:
        print('No test suites configured.', file=sys.stderr)
        return 2
    passed = 0
    for name, directory, pattern in suites:
        print(f'=== WP4a {name} ===', flush=True)
        if not any(directory.glob(pattern)):
            print(f'No test files found for {name}: {directory} / {pattern}', file=sys.stderr)
            continue
        result = subprocess.run(
            [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-p', pattern, '-v'],
            cwd=REPO,
            check=False,
        )
        passed += result.returncode == 0
    print(f'WP4a offline suites: {passed}/{len(suites)} passed', flush=True)
    return 0 if passed == len(suites) else 1


if __name__ == '__main__':
    sys.exit(run_suites())
