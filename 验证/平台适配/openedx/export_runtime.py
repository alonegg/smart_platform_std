"""Read native LMS tables and tracking logs, then invoke the pinned ERB processors."""

import collections
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from event_routing_backends.management.commands.helpers.event_log_parser import parse_json_event
from event_routing_backends.processors.caliper.envelope_processor import CaliperEnvelopeProcessor
from event_routing_backends.processors.caliper.transformer_processor import CaliperProcessor
from event_routing_backends.processors.xapi.transformer_processor import XApiProcessor

TABLES = (
    'courseware_studentmodule', 'courseware_studentmodulehistory',
    'grades_persistentcoursegrade', 'grades_persistentsubsectiongrade',
    'grades_persistentsubsectiongradeoverride', 'grades_historicalpersistentsubsectiongradeoverride',
    'grades_visibleblocks', 'student_courseenrollment', 'student_courseenrollment_history',
    'student_courseaccessrole', 'student_courseaccessrolehistory',
    'submissions_studentitem', 'submissions_submission', 'submissions_score', 'submissions_scoresummary',
    'assessment_assessment', 'assessment_assessmentpart', 'assessment_rubric',
    'assessment_criterion', 'assessment_criterionoption', 'assessment_staffworkflow',
    'workflow_assessmentworkflow', 'workflow_assessmentworkflowcancellation', 'workflow_assessmentworkflowstep',
    'course_groups_courseusergroup', 'course_groups_courseusergroup_users',
    'course_groups_coursecohort', 'course_groups_cohortmembership',
)
COURSE = "course_id LIKE %s"
ITEMS = f'SELECT id FROM submissions_studentitem WHERE {COURSE}'
SUBMISSIONS = f"SELECT REPLACE(uuid, '-', '') FROM submissions_submission WHERE student_item_id IN ({ITEMS})"
ASSESSMENT_SCOPE = f"REPLACE(submission_uuid, '-', '') IN ({SUBMISSIONS})"
ASSESSMENTS = f'SELECT id FROM assessment_assessment WHERE {ASSESSMENT_SCOPE}'
RUBRICS = f'SELECT rubric_id FROM assessment_assessment WHERE {ASSESSMENT_SCOPE}'
CRITERIA = f'SELECT id FROM assessment_criterion WHERE rubric_id IN ({RUBRICS})'
GROUPS = f'SELECT id FROM course_groups_courseusergroup WHERE {COURSE}'
FILTERS = {
    'courseware_studentmodulehistory': f'student_module_id IN (SELECT id FROM courseware_studentmodule WHERE {COURSE})',
    'grades_persistentsubsectiongradeoverride': f'grade_id IN (SELECT id FROM grades_persistentsubsectiongrade WHERE {COURSE})',
    'grades_historicalpersistentsubsectiongradeoverride': f'grade_id IN (SELECT id FROM grades_persistentsubsectiongrade WHERE {COURSE})',
    'submissions_submission': f'student_item_id IN ({ITEMS})',
    'submissions_score': f'student_item_id IN ({ITEMS})',
    'submissions_scoresummary': f'student_item_id IN ({ITEMS})',
    'assessment_assessment': ASSESSMENT_SCOPE,
    'assessment_assessmentpart': f'assessment_id IN ({ASSESSMENTS})',
    'assessment_rubric': f'id IN ({RUBRICS})',
    'assessment_criterion': f'rubric_id IN ({RUBRICS})',
    'assessment_criterionoption': f'criterion_id IN ({CRITERIA})',
    'workflow_assessmentworkflowcancellation': f'workflow_id IN (SELECT id FROM workflow_assessmentworkflow WHERE {COURSE})',
    'workflow_assessmentworkflowstep': f'workflow_id IN (SELECT id FROM workflow_assessmentworkflow WHERE {COURSE})',
    'course_groups_courseusergroup_users': f'courseusergroup_id IN ({GROUPS})',
    'course_groups_coursecohort': f'course_user_group_id IN ({GROUPS})',
}
SENSITIVE = re.compile(r'password|secret|token|session|cookie|csrf|authorization|api_key', re.I)
ROOT = Path(os.environ['WP4A_EXPORT_ROOT'])
ROOT.mkdir(parents=True, exist_ok=True)
assert not any(ROOT.iterdir()), 'Runtime export directory must be empty'
policy = {'removed_fields': {}, 'tables': list(TABLES),
          'scope': 'SYNTH/WP4A course_id selection plus explicit foreign-key/submission-UUID filters; auth_user is an explicit synthetic-user projection.',
          'tracking': 'Native JSON records; synthetic-course/user selection; sensitive keys and IP/agent removed. No session table export.'}


def scalar(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(type(value).__name__)


def clean(value):
    if isinstance(value, dict):
        return {key: clean(val) for key, val in value.items()
                if not SENSITIVE.search(key) and key not in ('ip', 'agent')}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=scalar) + '\n', encoding='utf-8')


users = list(get_user_model().objects.filter(username__startswith='wp4asynth').values(
    'id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff'))
assert len(users) == 4 and all(u['email'].endswith('@example.invalid') for u in users)
write('auth_user.json', users)
with connection.cursor() as cursor:
    for table in TABLES:
        cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} LIMIT 0')
        columns = [c[0] for c in cursor.description]
        condition = COURSE if 'course_id' in columns else FILTERS[table]
        query = f'SELECT * FROM {connection.ops.quote_name(table)} WHERE {condition}'
        cursor.execute(query, ['course-v1:SYNTH+WP4A+%'])
        rows = [clean(dict(zip(columns, row))) for row in cursor.fetchall()]
        assert rows, f'Missing required native evidence in {table}; seed all stages before export'
        policy['removed_fields'][table] = [name for name in columns if SENSITIVE.search(name)]
        write(table + '.json', rows)
    cursor.execute('SELECT user_id, name FROM auth_userprofile WHERE user_id IN (%s,%s,%s,%s)',
                   [u['id'] for u in users])
    write('auth_userprofile.json', [dict(zip(('user_id', 'name'), row)) for row in cursor.fetchall()])

events = []
source = Path('/openedx/data/logs/tracking.log')
for line in source.read_text(encoding='utf-8').splitlines():
    event = json.loads(line[line.index('{'):])
    context = event.get('context', {})
    payload = event.get('event', {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    course = context.get('course_id') or (payload.get('course_id') if isinstance(payload, dict) else '') or ''
    if course.startswith('course-v1:SYNTH+WP4A+') or event.get('username', '').startswith('wp4asynth'):
        events.append(clean(event))
assert events, 'No synthetic native tracking records found'
(ROOT / 'tracking.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events), encoding='utf-8')
write('export-policy.json', policy)

report = {'source': 'tracking.jsonl', 'configuration': {
    'CALIPER_EVENTS_ENABLED': True, 'XAPI_EVENTS_ENABLED': True,
    'CALIPER_EVENT_LOGGING_ENABLED': False, 'XAPI_EVENT_LOGGING_ENABLED': False,
    'delivery': 'Offline native ERB processor invocation inside LMS; no LRS/network delivery',
}, 'input_events': len(events), 'input_types': dict(collections.Counter(e['name'] for e in events)), 'formats': {}}
with override_settings(CALIPER_EVENTS_ENABLED=True, XAPI_EVENTS_ENABLED=True,
                       CALIPER_EVENT_LOGGING_ENABLED=False, XAPI_EVENT_LOGGING_ENABLED=False):
    for name, processor in (('xapi', XApiProcessor()), ('caliper', CaliperProcessor())):
        results = []
        detail = {'converted_inputs': 0, 'unsupported_types': {}, 'errors': [], 'empty_types': {}}
        for index, raw in enumerate(events):
            event = parse_json_event(json.dumps(deepcopy(raw)))
            kind = event['name']
            if kind not in processor.registry.mapping:
                detail['unsupported_types'][kind] = detail['unsupported_types'].get(kind, 0) + 1
                continue
            try:
                result = processor.transform_event(event)
                if not result:
                    detail['empty_types'][kind] = detail['empty_types'].get(kind, 0) + 1
                    continue
                batch = result if isinstance(result, list) else [result]
                if name == 'caliper':
                    batch = CaliperEnvelopeProcessor(settings.LMS_ROOT_URL)(batch)
                results.extend(batch)
                detail['converted_inputs'] += 1
            except Exception as error:
                detail['errors'].append({'input_line': index + 1, 'type': kind,
                                         'error_class': type(error).__name__, 'message': str(error)})
        (ROOT / f'{name}.jsonl').write_text(''.join(json.dumps(clean(e), ensure_ascii=False) + '\n' for e in results),
                                           encoding='utf-8')
        detail['output_records'] = len(results)
        report['formats'][name] = detail
write('erb-report.json', report)
print('EXPORTED native tables, tracking, and offline ERB output to', ROOT)
