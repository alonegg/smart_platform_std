"""Collect deployment metadata only; never export Tutor configuration or credentials."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
PROJECT = 'wp4a_openedx'
SERVICES = ('lms', 'cms', 'lms-worker', 'cms-worker', 'mysql', 'mongodb',
            'redis', 'caddy', 'meilisearch', 'permissions')
SNAPSHOT = {
    'edx-platform': 'ccfe30bfdb22d56c0139958c17049840b8176519',
    'edx-event-routing-backends': 'bae21257a259d17d54d9501af0abdd0c8e002ed8',
    'edx-submissions': '9c9e7c416a127c769b72d2c1b7141de96d20283a',
}


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def prepare_output(output):
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output must be an empty directory; existing files are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    return output


def collect():
    images = {}
    for service in SERVICES:
        name = f'{PROJECT}-{service}-1'
        # Select fields: never emit the environment (it contains runtime passwords).
        entry = json.loads(run('docker', 'inspect', '--format',
                               '{"image":{{json .Config.Image}},"image_id":{{json .Image}},'
                               '"status":{{json .State.Status}},"exit_code":{{.State.ExitCode}}}', name))
        entry['repo_digests'] = json.loads(run('docker', 'image', 'inspect', '--format',
                                               '{{json .RepoDigests}}', entry['image_id']))
        images[service] = entry
    script = '''
import importlib.metadata as m
import json, subprocess, sys
packages = {}
for name in ('edx-event-routing-backends', 'edx-submissions', 'ora2', 'openedx-events', 'Django'):
    dist = m.distribution(name)
    direct = json.loads(dist.read_text('direct_url.json') or '{}')
    packages[name] = {'version': dist.version, 'commit': direct.get('vcs_info', {}).get('commit_id')}
print(json.dumps({'python': sys.version.split()[0], 'packages': packages,
                  'edx-platform': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}))
'''
    platform = json.loads(run('docker', 'exec', f'{PROJECT}-lms-1', 'python', '-c', script))
    tutor = json.loads(run(str(ROOT / '.runtime/venv/bin/python'), '-c',
                          "import importlib.metadata as m,json; d=m.distribution('tutor'); "
                          "print(json.dumps({'version':d.version,'commit':json.loads("
                          "d.read_text('direct_url.json'))['vcs_info']['commit_id']}))"))
    runtime = {}
    for service, command in {
        'mysql': ['mysql', '--version'],
        'mongodb': ['mongod', '--version'],
        'redis': ['redis-server', '--version'],
        'caddy': ['caddy', 'version'],
        'meilisearch': ['meilisearch', '--version'],
    }.items():
        runtime[service] = run('docker', 'exec', f'{PROJECT}-{service}-1', *command)
    return {
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'evidence_level': '运行时部署元数据；教学证据需另查samples清单',
        'source_command': 'python3 collect_versions.py --output <empty-directory>',
        'snapshot': SNAPSHOT, 'tutor': tutor, 'platform': platform,
        'images': images, 'runtime_versions': runtime,
        'limitations': [
            'Derivative image is built locally and was not published; recorded digests do not imply registry availability.',
            'Wheel distributions without direct_url VCS metadata have unknown commits; versions are not commit evidence.',
            'Version metadata alone does not establish course, learner activity, xAPI or Caliper evidence.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    output = prepare_output(args.output if args.output is not None else
                            tempfile.mkdtemp(prefix='versions-', dir=runtime))
    (output / 'deployment.json').write_text(json.dumps(collect(), ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')
    print(f'Deployment metadata written to {output}')


if __name__ == '__main__':
    main()
