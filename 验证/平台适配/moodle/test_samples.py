import csv
import hashlib
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET

from export import COVERAGE, SCENARIO_ELEMENTS, make_manifest, prepare_output

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / 'samples'


def rows(name):
    return json.loads((SAMPLES / f'{name}.json').read_text(encoding='utf-8'))


class SamplesTest(unittest.TestCase):
    def test_manifest_integrity_and_complete_inventory(self):
        manifest = rows('manifest')
        self.assertTrue(manifest['deployed'])
        self.assertEqual(manifest['evidence_level'], '真实平台数据（合成课程/学员）')
        self.assertEqual({p.name for p in SAMPLES.iterdir()},
                         {'manifest.json'} | {f['file'] for f in manifest['files']})
        for entry in manifest['files']:
            data = (SAMPLES / entry['file']).read_bytes()
            self.assertEqual(entry['bytes'], len(data))
            self.assertEqual(entry['sha256'], hashlib.sha256(data).hexdigest())
            for key in ('source_command', 'collected_at', 'platform_version', 'coverage'):
                self.assertTrue(entry[key])
        self.assertLess(sum(p.stat().st_size for p in SAMPLES.iterdir()), 20_000_000)
        for service in ('web', 'db'):
            self.assertTrue(manifest['images'][service]['repo_digests'])
        self.assertEqual(manifest['platform']['commit'], '2d4bafe8548a6d6c01494c862ec3d9749ba6ea84')

    def test_traceability_exists_in_matrix_and_no_scope_omissions(self):
        self.assertEqual(set(COVERAGE), set(SCENARIO_ELEMENTS))
        self.assertEqual(rows('manifest')['scenario_elements'], SCENARIO_ELEMENTS)
        self.assertEqual(rows('manifest')['scenario_files'], COVERAGE)
        with (ROOT / '追溯表.csv').open(encoding='utf-8') as stream:
            trace = list(csv.DictReader(stream))
        with (ROOT.parents[1] / '平台对标/数据要素对照矩阵.csv').open(encoding='utf-8') as stream:
            known = {r[0] for r in csv.reader(stream)}
        expected = {(scenario, element) for scenario, elements in SCENARIO_ELEMENTS.items() for element in elements}
        actual = {(r['场景'], r['要素编号']) for r in trace}
        self.assertEqual(expected, actual)
        self.assertEqual(len(trace), len(expected))
        for row in trace:
            self.assertIn(row['要素编号'], known)
            self.assertEqual(set(row['样本文件'].split(';')), set(COVERAGE[row['场景']]))
            for name in row['样本文件'].split(';'):
                self.assertTrue((SAMPLES / name).is_file())
        for names in COVERAGE.values():
            for name in names:
                self.assertTrue((SAMPLES / name).is_file())

    def test_two_offerings_people_and_enrolment(self):
        courses = [r for r in rows('course') if r['shortname'].startswith('SYNTH-OPEN-')]
        self.assertEqual(len(courses), 2)
        users = [r for r in rows('user') if re.fullmatch(r'synthetic0[1-4]', r['username'])]
        self.assertEqual(len(users), 4)
        for course in courses:
            enrolids = {r['id'] for r in rows('enrol') if r['courseid'] == course['id']}
            self.assertEqual({r['userid'] for r in rows('user_enrolments') if r['enrolid'] in enrolids},
                             {r['id'] for r in users})
        updates = [r for r in rows('logstore_standard_log') if r['eventname'].endswith('user_enrolment_updated')]
        self.assertEqual(len(updates), 2)
        self.assertEqual(len({r['objectid'] for r in updates}), 1)
        teacher = next(r['id'] for r in users if r['username'] == 'synthetic04')
        teacherrole = next(r['id'] for r in rows('role') if r['shortname'] == 'editingteacher')
        self.assertEqual(len([r for r in rows('role_assignments') if r['userid'] == teacher and r['roleid'] == teacherrole]), 2)

    def test_video_views_and_embedded_video(self):
        video = next(r for r in rows('files') if r['filename'] == 'synthetic.mp4')
        self.assertEqual(video['mimetype'], 'video/mp4')
        views = [r for r in rows('logstore_standard_log') if r['eventname'] == '\\mod_resource\\event\\course_module_viewed']
        self.assertEqual(len({r['userid'] for r in views}), 3)
        self.assertTrue(all(r['origin'] == 'cli' for r in views))
        with tarfile.open(SAMPLES / 'course-users.mbz') as archive:
            member = 'files/' + video['contenthash'][:2] + '/' + video['contenthash']
            data = archive.extractfile(member).read()
            self.assertEqual(hashlib.sha1(data).hexdigest(), video['contenthash'])
            self.assertIn(b'ftyp', data[:32])

    def test_quiz_answers_and_grades(self):
        attempts = rows('quiz_attempts')
        self.assertEqual(len(attempts), 3)
        self.assertTrue(all(r['state'] == 'finished' and float(r['sumgrades']) == 1 for r in attempts))
        self.assertTrue(all(float(r['grade']) == 100 for r in rows('quiz_grades')))
        self.assertEqual(len(rows('quiz_grades')), 3)
        self.assertTrue(any(r['name'] == 'answer' and r['value'] == '2' for r in rows('question_attempt_step_data')))

    def test_assignment_reopen_two_submitted_attempts(self):
        assignment = next(r for r in rows('assign') if r['teamsubmission'] == '0')
        self.assertEqual(assignment['attemptreopenmethod'], 'manual')
        attempts = [r for r in rows('assign_submission') if r['assignment'] == assignment['id']]
        self.assertEqual({r['attemptnumber'] for r in attempts}, {'0', '1'})
        self.assertTrue(all(r['status'] == 'submitted' for r in attempts))
        self.assertEqual({r['latest'] for r in attempts}, {'0', '1'})
        texts = [r for r in rows('assignsubmission_onlinetext') if r['submission'] in {a['id'] for a in attempts}]
        self.assertEqual(len(texts), 2)
        self.assertEqual(len({r['onlinetext'] for r in texts}), 2)

    def test_teacher_grade_revision(self):
        assignment = next(r for r in rows('assign') if r['teamsubmission'] == '0')
        item = next(r for r in rows('grade_items') if r['itemmodule'] == 'assign' and r['iteminstance'] == assignment['id'])
        history = [r for r in rows('grade_grades_history') if r['itemid'] == item['id']]
        self.assertTrue({60, 70, 85}.issubset({float(r['finalgrade']) for r in history if r['finalgrade'] is not None}))
        current = [r for r in rows('grade_grades') if r['itemid'] == item['id'] and r['finalgrade'] is not None]
        self.assertEqual([float(r['finalgrade']) for r in current], [85])
        teacher = next(r['id'] for r in rows('user') if r['username'] == 'synthetic04')
        self.assertTrue(all(r['grader'] == teacher for r in rows('assign_grades')))

    def test_group_assignment_and_members(self):
        assignment = next(r for r in rows('assign') if r['teamsubmission'] == '1')
        link = next(r for r in rows('groupings_groups') if r['groupingid'] == assignment['teamsubmissiongroupingid'])
        self.assertEqual(len([r for r in rows('groups_members') if r['groupid'] == link['groupid']]), 3)
        self.assertTrue(any(r['assignment'] == assignment['id'] and r['groupid'] == link['groupid'] and
                            r['userid'] == '0' and r['status'] == 'submitted' for r in rows('assign_submission')))
        grades = [r for r in rows('assign_grades') if r['assignment'] == assignment['id']]
        self.assertEqual(len(grades), 3)
        self.assertTrue(all(float(r['grade']) == 85 for r in grades))

    def test_no_sensitive_json_and_only_synthetic_accounts(self):
        sensitive = re.compile(r'password|secret|token|sesskey|sessionid', re.I)
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertIsNone(sensitive.search(key), key)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                self.assertNotRegex(value, r'\$(?:2[ayb]\$|argon2)')
        for path in SAMPLES.glob('*.json'):
            if path.stem not in ('manifest', 'export_policy'):
                walk(json.loads(path.read_text(encoding='utf-8')))
        expected = {'guest', 'syntheticadmin', 'synthetic01', 'synthetic02', 'synthetic03', 'synthetic04'}
        self.assertEqual({r['username'] for r in rows('user')}, expected)
        for user in rows('user'):
            self.assertTrue(user['email'].endswith('@example.invalid') or
                            (user['username'] == 'guest' and user['email'] == 'root@localhost'))
        self.assertFalse(any(p.stem in {'sessions', 'user_password_history', 'external_tokens'} for p in SAMPLES.iterdir()))

    def test_backups_users_and_no_credentials(self):
        for filename, include_users in [('course-users.mbz', True), ('course-no-users.mbz', False)]:
            with tarfile.open(SAMPLES / filename) as archive:
                info = ET.fromstring(archive.extractfile('moodle_backup.xml').read())
                setting = {s.findtext('name'): s.findtext('value') for s in info.findall('information/settings/setting')
                           if s.findtext('level') == 'root'}
                self.assertEqual(setting['users'], str(int(include_users)))
                if include_users:
                    users = ET.fromstring(archive.extractfile('users.xml').read())
                    self.assertEqual(len(users), 4)
                    self.assertTrue(all(u.findtext('email').endswith('@example.invalid') for u in users))
                    self.assertEqual(setting['logs'], '1')
                    self.assertEqual(setting['grade_histories'], '1')
                else:
                    self.assertNotIn('users.xml', archive.getnames())
                for member in archive.getmembers():
                    if member.isfile() and member.name.endswith('.xml'):
                        root = ET.fromstring(archive.extractfile(member).read())
                        for node in root.iter():
                            if re.search(r'password|secret|token|sesskey|sessionid', node.tag, re.I):
                                self.assertIn(node.text, (None, '', '$@NULL@$'), (member.name, node.tag))

    def test_output_empty_and_nonempty_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = prepare_output(Path(tmp) / 'new')
            marker = output / 'existing'
            marker.write_text('unchanged')
            with self.assertRaises(ValueError):
                prepare_output(output)
            self.assertEqual(marker.read_text(), 'unchanged')
        with self.assertRaises(ValueError):
            prepare_output(SAMPLES)

    def test_manifest_rejects_missing_or_invalid_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                make_manifest(output, {})
            (output / 'platform.json').write_text('not json')
            with self.assertRaises(json.JSONDecodeError):
                make_manifest(output, {})


if __name__ == '__main__':
    unittest.main()
