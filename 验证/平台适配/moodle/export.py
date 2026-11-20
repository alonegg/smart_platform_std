"""Export raw Moodle synthetic-site evidence; never convert to standard contracts."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
COMMIT = '2d4bafe8548a6d6c01494c862ec3d9749ba6ea84'
COVERAGE = {
    'two_offerings': ['course.json'],
    'learners_and_teacher': ['user.json', 'role_assignments.json'],
    'enrolment_state_change': ['user_enrolments.json', 'logstore_standard_log.json'],
    'synthetic_video_resource_views': ['resource.json', 'files.json', 'logstore_standard_log.json'],
    'quiz_attempts_and_grading': ['quiz_attempts.json', 'quiz_grades.json', 'question_attempt_steps.json'],
    'assignment_reopen_resubmit': ['assign_submission.json', 'assignsubmission_onlinetext.json'],
    'teacher_grade_revision': ['assign_grades.json', 'grade_grades.json', 'grade_grades_history.json'],
    'group_assignment': ['groups.json', 'groups_members.json', 'groupings.json',
                         'groupings_groups.json', 'assign_submission.json'],
    'course_backups': ['course-users.mbz', 'course-no-users.mbz'],
}
SCENARIO_ELEMENTS = {
    'two_offerings': ['OBJ-004', 'OBJ-006'],
    'learners_and_teacher': ['OBJ-001', 'OBJ-010'],
    'enrolment_state_change': ['OBJ-007', 'EVT-002'],
    'synthetic_video_resource_views': ['OBJ-020', 'EVT-004'],
    'quiz_attempts_and_grading': ['OBJ-023', 'EVT-011'],
    'assignment_reopen_resubmit': ['OBJ-009', 'EVT-012', 'EVT-013'],
    'teacher_grade_revision': ['EVT-020'],
    'group_assignment': ['OBJ-012', 'FLD-EVT-014'],
    'course_backups': ['OBJ-029'],
}


def run(*args):
    return subprocess.check_output(args, cwd=BASE, text=True).strip()


def prepare_output(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ValueError('Output must be empty; existing samples are never overwritten')
    return path


def make_manifest(output, images):
    version = json.loads((output / 'platform.json').read_text(encoding='utf-8'))
    files = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for path in sorted(output.iterdir()):
        if path.name == 'manifest.json':
            continue
        command = ('docker compose exec -T web php /var/www/html/admin/cli/backup.php '
                   '--courseshortname=SYNTH-OPEN-01 --destination=<output>'
                   if path.name == 'course-users.mbz' else
                   'docker compose exec -T web php /work/export.php <output>')
        files.append({'file': path.name, 'bytes': path.stat().st_size,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'source_command': command, 'collected_at': now, 'platform_version': version,
                      'coverage': [k for k, names in COVERAGE.items() if path.name in names] or ['supporting_raw_evidence']})
    return {'evidence_level': '真实平台数据（合成课程/学员）', 'deployed': True,
            'source_snapshot_commit': COMMIT, 'platform': version, 'images': images,
            'scenario_files': COVERAGE, 'scenario_elements': SCENARIO_ELEMENTS, 'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--output', type=Path)
    target.add_argument('--update-samples', action='store_true')
    args = parser.parse_args()
    output = prepare_output(BASE / 'samples' if args.update_samples else
                            args.output or tempfile.mkdtemp(prefix='moodle-samples-'))
    runtime = BASE / '.runtime'
    stage = Path(tempfile.mkdtemp(prefix='export-', dir=runtime))
    container = '/work/.runtime/' + stage.name
    run('docker', 'compose', 'exec', '-T', 'web', 'php', '/work/export.php', container)
    run('docker', 'compose', 'exec', '-T', 'web', 'php', '/var/www/html/admin/cli/backup.php',
        '--courseshortname=SYNTH-OPEN-01', '--destination=' + container)
    backups = list(stage.glob('backup-*.mbz'))
    if len(backups) != 1:
        raise RuntimeError('Expected exactly one CLI backup')
    backups[0].rename(stage / 'course-users.mbz')
    images = {}
    for service in ('web', 'db'):
        cid = run('docker', 'compose', 'ps', '-q', service)
        actual = json.loads(run('docker', 'inspect', cid))[0]
        info = json.loads(run('docker', 'image', 'inspect', actual['Image']))[0]
        images[service] = {'name': actual['Config']['Image'], 'id': actual['Image'],
                           'repo_digests': info['RepoDigests']}
    manifest = make_manifest(stage, images)
    (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for path in stage.iterdir():
        shutil.copy2(path, output / path.name)
    print(f'Exported {len(manifest["files"])} files to {output}')


if __name__ == '__main__':
    main()
