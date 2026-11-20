"""Collect native synthetic Open edX evidence into a new directory only."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import uuid

from collect_versions import collect, prepare_output

ROOT = Path(__file__).resolve().parent
COVERAGE = {
    'two_offerings': ['run01.tar.gz', 'run02.tar.gz'],
    'people': ['auth_user.json', 'auth_userprofile.json', 'student_courseaccessrole.json'],
    'enrolment_change': ['student_courseenrollment.json', 'student_courseenrollment_history.json', 'tracking.jsonl'],
    'video_events': ['run01.tar.gz', 'tracking.jsonl'],
    'capa_checks': ['courseware_studentmodule.json', 'courseware_studentmodulehistory.json', 'tracking.jsonl'],
    'ora_reset_resubmit': ['submissions_submission.json', 'submissions_studentitem.json',
                           'workflow_assessmentworkflowcancellation.json', 'tracking.jsonl'],
    'assessment_revision': ['assessment_assessment.json', 'assessment_assessmentpart.json', 'submissions_score.json',
                            'grades_persistentsubsectiongradeoverride.json', 'grades_historicalpersistentsubsectiongradeoverride.json'],
    'cohorts': ['course_groups_courseusergroup.json', 'course_groups_cohortmembership.json'],
    'native_event_formats': ['tracking.jsonl', 'xapi.jsonl', 'caliper.jsonl', 'erb-report.json'],
}
SCENARIO_ELEMENTS = {
    'two_offerings': ['OBJ-004', 'OBJ-006'], 'people': ['OBJ-001', 'OBJ-010'],
    'enrolment_change': ['OBJ-007', 'EVT-002'], 'video_events': ['OBJ-020', 'EVT-004'],
    'capa_checks': ['OBJ-009', 'EVT-011'], 'ora_reset_resubmit': ['OBJ-009', 'EVT-013'],
    'assessment_revision': ['EVT-020'], 'cohorts': ['OBJ-012', 'FLD-EVT-014'],
    'native_event_formats': ['OBJ-029', 'FLD-EVT-004'],
}


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def make_manifest(output, platform):
    required = {name for names in COVERAGE.values() for name in names}
    missing = required - {path.name for path in output.iterdir() if path.is_file()}
    if missing:
        raise ValueError('Missing scenario evidence: ' + ', '.join(sorted(missing)))
    timestamp = datetime.now(timezone.utc).isoformat()
    files = []
    for path in sorted(output.iterdir()):
        if path.name == 'manifest.json':
            continue
        data = path.read_bytes()
        scenarios = [key for key, names in COVERAGE.items() if path.name in names]
        source = 'LMS Django shell: export_runtime.py; selected native SQL table or runtime processor output'
        if path.suffixes[-2:] == ['.tar', '.gz']:
            source = './manage.py cms export course-v1:SYNTH+WP4A+' + path.name.split('.')[0] + ' <new-directory>; tarfile gzip archive'
        elif path.name == 'platform.json':
            source = 'collect_versions.collect(): selected docker inspect fields and in-container version commands'
        files.append({'file': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'source_command': source, 'collected_at': timestamp,
                      'platform_version': platform['platform']['edx-platform'],
                      'coverage': scenarios or ['supporting_metadata']})
    return {'evidence_level': '真实平台数据（合成课程/学员）', 'deployed': True,
            'collected_at': timestamp, 'platform': platform, 'files': files,
            'scenario_files': COVERAGE, 'scenario_elements': SCENARIO_ELEMENTS,
            'not_claimed': ['standard-contract conversion', 'certification', 'actual browser video playback',
                            'immutable course versions', 'real educational effectiveness', 'LRS delivery']}


def export(output):
    remote = '/tmp/wp4a-export-' + uuid.uuid4().hex
    run('docker', 'cp', str(ROOT / 'export_runtime.py'), 'wp4a_openedx-lms-1:/tmp/wp4a-export_runtime.py')
    run('docker', 'exec', '-e', 'WP4A_EXPORT_ROOT=' + remote, 'wp4a_openedx-lms-1', './manage.py', 'lms', 'shell', '-c',
        "exec(compile(open('/tmp/wp4a-export_runtime.py').read(), '/tmp/wp4a-export_runtime.py', 'exec'))")
    run('docker', 'cp', 'wp4a_openedx-lms-1:' + remote + '/.', str(output))
    work = Path(tempfile.mkdtemp(prefix='olx-', dir=ROOT / '.runtime'))
    for name in ('run01', 'run02'):
        target = remote + '/' + name
        run('docker', 'exec', 'wp4a_openedx-cms-1', 'mkdir', '-p', target)
        run('docker', 'exec', 'wp4a_openedx-cms-1', './manage.py', 'cms', 'export',
            'course-v1:SYNTH+WP4A+' + name, target)
        run('docker', 'cp', 'wp4a_openedx-cms-1:' + target, str(work / name))
        with tarfile.open(output / (name + '.tar.gz'), 'w:gz') as archive:
            archive.add(work / name, arcname=name)
    platform = collect()
    platform['evidence_level'] = '运行时部署与本次合成样本关联版本元数据'
    (output / 'platform.json').write_text(json.dumps(platform, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = make_manifest(output, platform)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(manifest["files"])} files to {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--output', type=Path)
    group.add_argument('--update-samples', action='store_true')
    args = parser.parse_args()
    (ROOT / '.runtime').mkdir(exist_ok=True)
    target = ROOT / 'samples' if args.update_samples else args.output
    output = prepare_output(target if target is not None else tempfile.mkdtemp(prefix='exports-', dir=ROOT / '.runtime'))
    export(output)


if __name__ == '__main__':
    main()
