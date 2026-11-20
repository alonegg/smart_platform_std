"""Run isolated synthetic scenarios against the existing Tutor deployment."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def shell(service, code):
    run('docker', 'exec', f'wp4a_openedx-{service}-1', './manage.py', service, 'shell', '-c', code)


def run_script(name):
    target = '/tmp/wp4a-' + name
    run('docker', 'cp', str(ROOT / name), 'wp4a_openedx-lms-1:' + target)
    shell('lms', f"exec(compile(open({target!r}).read(), {target!r}, 'exec'))")


def structure():
    shell('lms', "from django.contrib.auth import get_user_model; "
          "from openedx.core.djangoapps.content.course_overviews.models import CourseOverview; "
          "assert not get_user_model().objects.filter(username__startswith='wp4asynth').exists(), 'Seed users already exist'; "
          "assert not CourseOverview.objects.filter(id__startswith='course-v1:SYNTH+WP4A+').exists(), 'Seed courses already exist'")
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='seed-', dir=runtime))
    template = (ROOT / 'course-template.xml').read_text(encoding='utf-8')
    for name in ('run01', 'run02'):
        course = work / name
        (course / 'static').mkdir(parents=True)
        (course / 'course.xml').write_text(template.replace('__RUN__', name), encoding='utf-8')
        policies = course / 'policies' / name
        policies.mkdir(parents=True)
        (policies / 'grading_policy.json').write_text(json.dumps({
            'GRADER': [{'type': 'Homework', 'min_count': 1, 'drop_count': 0, 'short_label': 'HW', 'weight': 1}],
            'GRADE_CUTOFFS': {'Pass': 0.5},
        }), encoding='utf-8')
        run('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:d=3',
            '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(course / 'static/synthetic.mp4'))
    run('docker', 'exec', 'wp4a_openedx-cms-1', 'mkdir', '-p', '/tmp/wp4a-courses')
    run('docker', 'cp', str(work) + '/.', 'wp4a_openedx-cms-1:/tmp/wp4a-courses')
    run('docker', 'exec', 'wp4a_openedx-cms-1', './manage.py', 'cms', 'import',
        '/tmp/wp4a-courses', 'run01', 'run02')
    run_script('seed_structure.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['structure'], required=True)
    args = parser.parse_args()
    if args.stage == 'structure':
        structure()


if __name__ == '__main__':
    main()
