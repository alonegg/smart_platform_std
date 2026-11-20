"""Exercise the native staff reset, second ORA response, and grade overrides."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.db import connection
from edx_django_utils.cache import RequestCache
from opaque_keys.edx.keys import CourseKey
from lms.djangoapps.courseware.block_render import get_block_by_usage_id
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.grades.models import PersistentSubsectionGrade, PersistentSubsectionGradeOverride
from openassessment.runtime_imports.functions import reset_student_attempts
from openassessment.xblock.apis.submissions.submissions_actions import submit
from openassessment.xblock.apis.assessments.staff_assessment_api import do_staff_assessment
from xmodule.modulestore.django import modulestore

key = CourseKey.from_string('course-v1:SYNTH+WP4A+run01')
learner = get_user_model().objects.get(username='wp4asynth01')
teacher = get_user_model().objects.get(username='wp4asynth04')
assert not PersistentSubsectionGradeOverride.objects.filter(grade__course_id=key).exists(), 'Revision already exists'
with connection.cursor() as cursor:
    cursor.execute('SELECT s.status FROM submissions_submission s JOIN submissions_studentitem i '
                   'ON s.student_item_id=i.id WHERE i.course_id=%s', [str(key)])
    assert cursor.fetchall() == (('A',),), 'Expected exactly one active initial submission; partial/repeated revision refused'
descriptor, = modulestore().get_items(key, qualifiers={'category': 'openassessment'})


def ora_for(user):
    request = RequestFactory().get('/', HTTP_HOST='local.openedx.io')
    request.user = user
    SessionMiddleware(lambda r: None).process_request(request)
    block, _ = get_block_by_usage_id(request, str(key), str(descriptor.location))
    return block


old = ora_for(learner)
assert old.submission_uuid, 'Run learning first'
old_uuid = old.submission_uuid
reset_student_attempts(key, learner, descriptor.location, teacher, True)
RequestCache.clear_all_namespaces()
ora = ora_for(learner)
assert not ora.submission_uuid, 'Native reset did not clear the ORA state'
submit(['合成重交：我检查了加法，并补充说明。'], ora.config_data, ora.submission_data, ora.workflow_data)
ora.save()
assert ora.submission_uuid != old_uuid
teacher_ora = ora_for(teacher)
do_staff_assessment(ora.submission_uuid, {'clarity': 'clear'}, {}, '合成重交后评分', 'full-grade',
                    teacher_ora.config_data, teacher_ora.staff_assessment_data)
CourseGradeFactory().update(learner, course_key=key, force_update_subsections=True)
subsection, = modulestore().get_items(key, qualifiers={'category': 'sequential'})
grade = PersistentSubsectionGrade.objects.get(user_id=learner.pk, course_id=key, usage_key=subsection.location)
for earned, comment in ((2, '合成初次分数覆盖'), (3.5, '合成复核改分')):
    PersistentSubsectionGradeOverride.update_or_create_override(
        teacher, grade, earned_all_override=earned, earned_graded_override=earned,
        possible_all_override=4, possible_graded_override=4, comment=comment, system='wp4a-synthetic',
    )
CourseGradeFactory().update(learner, course_key=key)
print('REVISION: native staff reset, second ORA submission, staff score, two override history records')
