"""Execute through the LMS Django shell, after importing the two OLX runs."""

from django.contrib.auth import get_user_model
from common.djangoapps.student.models import CourseEnrollment, UserProfile
from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.course_groups import cohorts
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

User = get_user_model()
assert not User.objects.filter(username__startswith='wp4asynth').exists(), 'Seed users already exist'
users = []
for number in range(1, 5):
    user = User.objects.create_user(username=f'wp4asynth{number:02}', email=f'wp4asynth{number:02}@example.invalid')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.name = f'学员{number:02}' if number < 4 else '教师01'
    profile.save()
    users.append(user)

for run in ('run01', 'run02'):
    key = CourseKey.from_string(f'course-v1:SYNTH+WP4A+{run}')
    course = modulestore().get_course(key)
    assert course is not None
    video, = modulestore().get_items(key, qualifiers={'category': 'video'})
    assert not video.youtube_id_1_0, 'Only the synthetic HTML5 source is permitted'
    CourseOverview.load_from_module_store(key)
    for user in users:
        CourseEnrollment.enroll(user, key, mode='audit')
    CourseEnrollment.unenroll(users[2], key)
    CourseEnrollment.enroll(users[2], key, mode='audit')
    CourseStaffRole(key).add_users(users[3])
    CourseInstructorRole(key).add_users(users[3])
    cohorts.set_course_cohorted(key, True)
    cohort = cohorts.add_cohort(key, '合成小组01', 'manual')
    for user in users[:3]:
        cohorts.add_user_to_cohort(cohort, user)
    print(f'STRUCTURE SEEDED {key}: 3 learners, teacher, unenrol/re-enrol, cohort')
