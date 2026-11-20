"""Offline checks of native synthetic evidence, provenance and output safety."""

import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import uuid
import xml.etree.ElementTree as ET

import export as collector

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / 'samples'
SENSITIVE = re.compile(r'password|secret|token|session|cookie|csrf|authorization|api_key', re.I)
EMAIL = re.compile(r'[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9_-])')


def read(name):
    return json.loads((SAMPLES / name).read_text(encoding='utf-8'))


def lines(name):
    return [json.loads(line) for line in (SAMPLES / name).read_text(encoding='utf-8').splitlines()]


class SamplesTest(unittest.TestCase):
    def test_manifest_inventory_hashes_and_size(self):
        manifest = read('manifest.json')
        self.assertEqual(manifest['evidence_level'], '真实平台数据（合成课程/学员）')
        inventory = manifest['files']
        names = [entry['file'] for entry in inventory]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), {p.name for p in SAMPLES.iterdir()} - {'manifest.json'})
        self.assertLess(sum(p.stat().st_size for p in SAMPLES.iterdir()), 20 * 1024 * 1024)
        for entry in inventory:
            path = SAMPLES / entry['file']
            self.assertTrue(path.is_file())
            data = path.read_bytes()
            self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry['bytes'], len(data))
            for field in ('source_command', 'platform_version', 'collected_at', 'coverage'):
                self.assertTrue(entry[field])
        platform = manifest['platform']
        self.assertEqual(platform, read('platform.json'))
        self.assertEqual(platform['platform']['packages']['edx-event-routing-backends']['commit'],
                         'bae21257a259d17d54d9501af0abdd0c8e002ed8')
        for image in platform['images'].values():
            self.assertTrue(image['image_id'].startswith('sha256:'))
            self.assertTrue(image['repo_digests'])

    def test_two_native_olx_runs_and_synthetic_media(self):
        for run in ('run01', 'run02'):
            with tarfile.open(SAMPLES / f'{run}.tar.gz') as archive:
                members = archive.getmembers()
                for member in members:
                    self.assertFalse(Path(member.name).is_absolute())
                    self.assertNotIn('..', Path(member.name).parts)
                    self.assertFalse(member.issym() or member.islnk())
                def xml(name):
                    return ET.fromstring(archive.extractfile(f'{run}/{name}').read())
                self.assertEqual(xml('course.xml').attrib, {'org': 'SYNTH', 'course': 'WP4A', 'url_name': run})
                video = xml('video/video.xml')
                self.assertEqual(video.attrib.get('youtube_id_1_0'), '')
                self.assertFalse(video.attrib.get('youtube'))
                self.assertEqual(video.find('source').attrib['src'], '/static/synthetic.mp4')
                self.assertIn(b'ftyp', archive.extractfile(f'{run}/static/synthetic.mp4').read(32))
                self.assertEqual(xml('problem/addition.xml').find('numericalresponse').attrib['answer'], '2')
                ora = xml('vertical/unit.xml').find('openassessment')
                self.assertIsNotNone(ora)
                self.assertEqual(ora.find('assessments/assessment').attrib['name'], 'staff-assessment')
                self.assertEqual(ora.attrib['allow_learner_resubmissions'], 'False')

    def test_privacy_including_nested_states_and_olx(self):
        def check(value):
            if isinstance(value, dict):
                for key, val in value.items():
                    self.assertIsNone(SENSITIVE.search(key), key)
                    check(val)
            elif isinstance(value, list):
                for item in value:
                    check(item)
            elif isinstance(value, str):
                self.assertNotRegex(value, r'pbkdf2_sha256\$|argon2\$|-----BEGIN .*PRIVATE KEY|Bearer [A-Za-z0-9]')
                for email in EMAIL.findall(value):
                    self.assertTrue(email.endswith('@example.invalid'), email)
                if value.startswith(('{', '[')):
                    try:
                        nested = json.loads(value)
                    except json.JSONDecodeError:
                        return
                    check(nested)
        for path in SAMPLES.iterdir():
            if path.suffix == '.json':
                check(read(path.name))
            elif path.suffix == '.jsonl':
                check(lines(path.name))
            elif path.suffix == '.gz':
                with tarfile.open(path) as archive:
                    for member in archive.getmembers():
                        if not member.isfile() or member.name.endswith('.mp4'):
                            continue
                        text = archive.extractfile(member).read().decode('utf-8')
                        check(text)
                        if member.name.endswith('.xml'):
                            for node in ET.fromstring(text).iter():
                                self.assertIsNone(SENSITIVE.search(node.tag))
                                check(node.attrib)

    def test_synthetic_people_roles_and_foreign_keys(self):
        users = read('auth_user.json')
        usernames = {f'wp4asynth{n:02}' for n in range(1, 5)}
        self.assertEqual({u['username'] for u in users}, usernames)
        self.assertTrue(all(u['email'] == u['username'] + '@example.invalid' for u in users))
        self.assertEqual({u['name'] for u in read('auth_userprofile.json')}, {'学员01', '学员02', '学员03', '教师01'})
        ids = {u['id'] for u in users}
        teacher = next(u['id'] for u in users if u['username'] == 'wp4asynth04')
        for run in ('run01', 'run02'):
            roles = [r for r in read('student_courseaccessrole.json') if r['course_id'].endswith(run)]
            self.assertEqual({(r['user_id'], r['role']) for r in roles}, {(teacher, 'staff'), (teacher, 'instructor')})
        for path in SAMPLES.glob('*.json'):
            rows = read(path.name)
            if not isinstance(rows, list):
                continue
            for row in rows:
                for name in ('user_id', 'student_id', 'history_user_id', 'changed_by_id', 'cancelled_by_id'):
                    value = row.get(name)
                    if isinstance(value, int):
                        self.assertIn(value, ids, (path.name, name, value))
        for event in lines('tracking.jsonl'):
            self.assertIn(event.get('username', ''), usernames | {''})
            user_id = event.get('context', {}).get('user_id')
            if user_id not in (None, 'None', '', 0):
                self.assertIn(int(user_id), ids)

    def test_enrolment_history_and_cohorts(self):
        users = {u['username']: u['id'] for u in read('auth_user.json')}
        for run in ('run01', 'run02'):
            course = 'course-v1:SYNTH+WP4A+' + run
            enrolments = [r for r in read('student_courseenrollment.json') if r['course_id'] == course]
            self.assertEqual(len(enrolments), 4)
            self.assertTrue(all(r['is_active'] and r['mode'] == 'audit' for r in enrolments))
            history = sorted((r for r in read('student_courseenrollment_history.json')
                              if r['course_id'] == course and r['user_id'] == users['wp4asynth03']),
                             key=lambda r: r['history_date'])
            self.assertTrue(any(not r['is_active'] for r in history))
            self.assertTrue(history[-1]['is_active'])
            groups = [g for g in read('course_groups_courseusergroup.json') if g['course_id'] == course]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]['group_type'], 'cohort')
            members = [r for r in read('course_groups_cohortmembership.json') if r['course_id'] == course]
            self.assertEqual({r['user_id'] for r in members}, {users[f'wp4asynth{n:02}'] for n in range(1, 4)})
            self.assertEqual({r['course_user_group_id'] for r in members}, {groups[0]['id']})

    def test_video_and_capa_native_state_history(self):
        events = lines('tracking.jsonl')
        counts = collections.Counter(e['name'] for e in events)
        for kind in ('play_video', 'pause_video', 'stop_video'):
            self.assertEqual(counts[kind], 3)
            self.assertEqual({e['username'] for e in events if e['name'] == kind},
                             {f'wp4asynth{n:02}' for n in range(1, 4)})
        self.assertEqual(counts['problem_check'], 6)
        problems = [m for m in read('courseware_studentmodule.json') if m['module_type'] == 'problem']
        self.assertEqual(len(problems), 3)
        for module in problems:
            self.assertEqual((module['grade'], module['max_grade']), (1, 1))
            self.assertEqual(json.loads(module['state'])['attempts'], 2)
            history = [h for h in read('courseware_studentmodulehistory.json') if h['student_module_id'] == module['id']]
            self.assertEqual({h['grade'] for h in history}, {0, 1})
            self.assertEqual({json.loads(h['state'])['attempts'] for h in history}, {1, 2})

    def test_ora_reset_resubmit_assessment_and_override_history(self):
        submissions = read('submissions_submission.json')
        self.assertEqual(len(submissions), 2)
        self.assertEqual({s['status'] for s in submissions}, {'A', 'D'})
        self.assertEqual(len({s['uuid'] for s in submissions}), 2)
        self.assertEqual(len({s['student_item_id'] for s in submissions}), 1)
        self.assertEqual({s['attempt_number'] for s in submissions}, {1})
        self.assertEqual(len({s['raw_answer'] for s in submissions}), 2)
        self.assertEqual(len(read('workflow_assessmentworkflowcancellation.json')), 1)
        assessments = read('assessment_assessment.json')
        self.assertEqual(len(assessments), 3)
        self.assertEqual({uuid.UUID(a['submission_uuid']).hex for a in assessments},
                         {uuid.UUID(s['uuid']).hex for s in submissions})
        self.assertEqual(len(read('assessment_assessmentpart.json')), 3)
        scores = read('submissions_score.json')
        self.assertTrue(any(s['reset'] for s in scores))
        self.assertTrue(any(float(s['points_earned']) == 3 for s in scores))
        overrides = read('grades_persistentsubsectiongradeoverride.json')
        self.assertEqual(len(overrides), 1)
        self.assertEqual(float(overrides[0]['earned_all_override']), 3.5)
        history = read('grades_historicalpersistentsubsectiongradeoverride.json')
        self.assertEqual([float(h['earned_all_override']) for h in sorted(history, key=lambda h: h['history_id'])], [2, 3.5])
        self.assertTrue(all(float(h['possible_all_override']) == 4 for h in history))
        self.assertEqual(len(read('grades_persistentcoursegrade.json')), 3)

    def test_erb_native_outputs_and_explicit_gaps(self):
        events = lines('tracking.jsonl')
        report = read('erb-report.json')
        self.assertEqual(report['input_events'], len(events))
        self.assertEqual(report['input_types'], dict(collections.Counter(e['name'] for e in events)))
        for name in ('xapi', 'caliper'):
            detail = report['formats'][name]
            output = lines(name + '.jsonl')
            self.assertGreater(len(output), 0)
            self.assertEqual(detail['output_records'], len(output))
            accounted = (detail['converted_inputs'] + sum(detail['unsupported_types'].values())
                         + sum(detail['empty_types'].values()) + len(detail['errors']))
            self.assertEqual(accounted, len(events))
            self.assertIn('openassessmentblock.create_submission', detail['unsupported_types'])
        xapi = lines('xapi.jsonl')
        self.assertTrue(all({'actor', 'verb', 'object', 'timestamp'} <= e.keys() for e in xapi))
        self.assertTrue(any('video' in json.dumps(e).lower() for e in xapi))
        envelopes = lines('caliper.jsonl')
        self.assertTrue(all(e['dataVersion'].startswith('http://purl.imsglobal.org/ctx/caliper/') and e['data'] for e in envelopes))
        errors = report['formats']['xapi']['errors']
        self.assertEqual(len(errors), 6)
        for error in errors:
            source = events[error['input_line'] - 1]
            self.assertEqual(source['name'], 'problem_check')
            self.assertFalse(source.get('referer') or source['context'].get('referer'))
            self.assertEqual(error['error_class'], 'ValueError')
            self.assertIn('context.referer', error['message'])
        self.assertEqual(report['formats']['caliper']['errors'], [])

    def test_traceability_and_declared_scope_have_no_omissions(self):
        manifest = read('manifest.json')
        self.assertEqual(manifest['scenario_files'], collector.COVERAGE)
        self.assertEqual(manifest['scenario_elements'], collector.SCENARIO_ELEMENTS)
        matrix = ROOT.parents[1] / '平台对标' / '数据要素对照矩阵.csv'
        with matrix.open(encoding='utf-8-sig', newline='') as handle:
            ids = {row['要素编号'] for row in csv.DictReader(handle)}
        with (ROOT / '追溯表.csv').open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        expected = {(scenario, element) for scenario, elements in collector.SCENARIO_ELEMENTS.items() for element in elements}
        self.assertEqual({(row['场景'], row['要素编号']) for row in rows}, expected)
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            self.assertIn(row['要素编号'], ids)
            self.assertTrue(row['证据边界'])
            self.assertEqual(set(row['样本文件'].split(';')), set(collector.COVERAGE[row['场景']]))
            for name in row['样本文件'].split(';'):
                self.assertTrue((SAMPLES / name).is_file())


class OutputSafetyTest(unittest.TestCase):
    def test_manifest_normal_empty_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            platform = {'platform': {'edx-platform': 'test-version'}}
            with self.assertRaisesRegex(ValueError, 'Missing scenario evidence'):
                collector.make_manifest(output, platform)
            names = {n for values in collector.COVERAGE.values() for n in values}
            for name in names:
                (output / name).write_bytes(b'unit fixture, not platform evidence')
            self.assertEqual(len(collector.make_manifest(output, platform)['files']), len(names))
            (output / 'tracking.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'tracking.jsonl'):
                collector.make_manifest(output, platform)

    def test_default_output_is_private_and_never_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            samples = root / 'samples'
            samples.mkdir()
            sentinel = samples / 'committed'
            sentinel.write_bytes(b'unchanged')
            with patch.object(collector, 'ROOT', root), patch.object(sys, 'argv', ['export.py']), patch.object(collector, 'export') as run:
                collector.main()
                output, = run.call_args.args
                self.assertEqual(output.parent, root / '.runtime')
                self.assertEqual(list(output.iterdir()), [])
            self.assertEqual(sentinel.read_bytes(), b'unchanged')

    def test_real_cli_rejects_existing_samples_and_bad_arguments(self):
        before = {p.name: p.read_bytes() for p in SAMPLES.iterdir()}
        for args, message in ((['--update-samples'], 'existing files are never overwritten'),
                              (['--output', str(SAMPLES)], 'existing files are never overwritten'),
                              (['--unknown'], 'unrecognized arguments'),
                              (['--output', 'unused', '--update-samples'], 'not allowed with argument')):
            result = subprocess.run([sys.executable, str(ROOT / 'export.py'), *args], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in SAMPLES.iterdir()})


if __name__ == '__main__':
    unittest.main()
