"""Synthetic LMS requests and native ORA APIs; run in the LMS Django shell."""

import json
import re

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory
from eventtracking.tracker import get_tracker
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.safe_sessions.middleware import SafeSessionMiddleware
from lms.djangoapps.courseware.block_render import get_block_by_usage_id
from lms.djangoapps.courseware.models import StudentModule
from openassessment.xblock.apis.submissions.submissions_actions import submit
from openassessment.xblock.apis.assessments.staff_assessment_api import do_staff_assessment
from xmodule.modulestore.django import modulestore

key = CourseKey.from_string('course-v1:SYNTH+WP4A+run01')
users = list(get_user_model().objects.filter(username__startswith='wp4asynth').order_by('username'))
assert len(users) == 4, 'Run structure first'
assert not StudentModule.objects.filter(course_id=key, student=users[0]).exists(), 'Learning state already exists'
tracker = get_tracker()


def block_for(user, category):
    descriptor, = modulestore().get_items(key, qualifiers={'category': category})
    request = RequestFactory().get('/', HTTP_HOST='local.openedx.io')
    request.user = user
    SessionMiddleware(lambda r: None).process_request(request)
    block, context = get_block_by_usage_id(request, str(key), str(descriptor.location))
    return block, context


for user in users[:3]:
    client = Client(HTTP_HOST='local.openedx.io')
    client.force_login(user)
    SafeSessionMiddleware.update_with_safe_session_cookie(client.cookies, user.pk)
    video, _ = block_for(user, 'video')
    for event_type, position in (('play_video', 0), ('pause_video', 1), ('stop_video', 3)):
        response = client.post('/event', {
            'event_type': event_type,
            'event': json.dumps({'id': str(video.location), 'currentTime': position,
                                 'duration': 3, 'code': 'html5', 'speed': 1}),
            'page': f'http://local.openedx.io/courses/{key}/courseware/chapter/homework/',
            'context': json.dumps({'course_id': str(key)}),
        })
        assert response.status_code == 200, (response.status_code, response.content[:300])
    problem, _ = block_for(user, 'problem')
    html = problem.get_problem_html()
    names = set(re.findall(r'name=[\"\x27](input_[^\"\x27]+)', html))
    assert len(names) == 1, names
    url = problem.runtime.handler_url(problem, 'xmodule_handler', 'problem_check')
    for answer in ('1', '2'):
        response = client.post(url, {next(iter(names)): answer})
        assert response.status_code == 200, (response.status_code, response.content[:300])
        result = response.json()
        assert result['success'] == ('incorrect' if answer == '1' else 'correct'), result.get('success')
    client.logout()
    print(f'LEARNING: {user.username}: video events and two CAPA checks')

learner = users[0]
ora, context = block_for(learner, 'openassessment')
with tracker.context('wp4a', {'course_id': str(key), 'user_id': learner.id, 'username': learner.username}):
    with tracker.context('module', context):
        submit(['合成初稿：我用加法完成练习。'], ora.config_data, ora.submission_data, ora.workflow_data)
        ora.save()
first_uuid = ora.submission_uuid
teacher_ora, _ = block_for(users[3], 'openassessment')
do_staff_assessment(first_uuid, {'clarity': 'draft'}, {}, '合成初评', 'full-grade',
                    teacher_ora.config_data, teacher_ora.staff_assessment_data)
do_staff_assessment(first_uuid, {'clarity': 'clear'}, {}, '合成复核改分', 'regrade',
                    teacher_ora.config_data, teacher_ora.staff_assessment_data)
print('ORA: native submission and staff assessment/regrade completed', first_uuid)
