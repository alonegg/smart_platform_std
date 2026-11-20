<?php
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->libdir . '/testing/generator/lib.php');
require_once($CFG->dirroot . '/group/lib.php');
require_once($CFG->dirroot . '/mod/resource/lib.php');
require_once($CFG->dirroot . '/mod/assign/locallib.php');
require_once($CFG->dirroot . '/mod/quiz/locallib.php');
if ($DB->record_exists('course', ['shortname' => 'SYNTH-OPEN-01'])) {
    throw new RuntimeException('Seed already exists; teardown --volumes then deploy for a fresh run.');
}
set_config('enabled_stores', 'logstore_standard', 'tool_log');
set_config('loglifetime', 0, 'logstore_standard');
set_config('disablegradehistory', 0);
set_config('backup_general_users', 1, 'backup');
set_config('backup_general_userscompletion', 1, 'backup');
set_config('backup_general_logs', 1, 'backup');
set_config('backup_general_histories', 1, 'backup');
set_config('backup_general_anonymize', 0, 'backup');
$tx = $DB->start_delegated_transaction();
\core\session\manager::set_user(get_admin());
$g = new testing_data_generator();
$people = [];
for ($i = 1; $i <= 4; $i++) {
    $people[] = $g->create_user([
        'username' => sprintf('synthetic%02d', $i),
        'firstname' => $i == 4 ? '教师' : '学员', 'lastname' => sprintf('%02d', $i),
        'email' => sprintf('synthetic%02d@example.invalid', $i),
        'firstnamephonetic' => '', 'lastnamephonetic' => '', 'middlename' => '', 'alternatename' => '',
        'password' => bin2hex(random_bytes(24)),
    ]);
}
[$s1, $s2, $s3, $teacher] = $people;
$courses = [];
for ($i = 1; $i <= 2; $i++) {
    $course = $g->create_course(['shortname' => sprintf('SYNTH-OPEN-%02d', $i),
        'fullname' => '合成课程 开课' . $i, 'idnumber' => 'SYNTH-COURSE-01-OPEN-' . $i,
        'summary' => '同一合成教学主题的独立开课空间；不表示不可变课程版本。',
        'numsections' => 2]);
    $courses[] = $course;
    foreach ($people as $p) {
        $g->enrol_user($p->id, $course->id, $p->id == $teacher->id ? 'editingteacher' : 'student');
    }
}
$course = $courses[0];
$manual = enrol_get_plugin('manual');
$enrol = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
$manual->update_user_enrol($enrol, $s3->id, ENROL_USER_SUSPENDED);
$manual->update_user_enrol($enrol, $s3->id, ENROL_USER_ACTIVE);
$grouping = $g->create_grouping(['courseid' => $course->id, 'name' => '合成分组', 'idnumber' => 'SYNTH-GROUPING']);
$group = $g->create_group(['courseid' => $course->id, 'name' => '合成小组01']);
$g->create_grouping_group(['groupingid' => $grouping->id, 'groupid' => $group->id]);
foreach ([$s1, $s2, $s3] as $p) {
    groups_add_member($group->id, $p->id);
}
$video = $g->create_module('resource', ['course' => $course->id, 'name' => '三秒合成视频', 'display' => 0]);
$context = context_module::instance($video->cmid);
$file = get_file_storage()->create_file_from_pathname([
    'contextid' => $context->id, 'component' => 'mod_resource', 'filearea' => 'content',
    'itemid' => 0, 'filepath' => '/', 'filename' => 'synthetic.mp4', 'mimetype' => 'video/mp4',
    'sortorder' => 1], '/work/.runtime/synthetic.mp4');
foreach ([$s1, $s2, $s3] as $p) {
    \core\session\manager::set_user($p);
    $cm = get_coursemodule_from_id('resource', $video->cmid);
    resource_view($video, $course, $cm, $context);
}
\core\session\manager::set_user($teacher);
$quiz = $g->create_module('quiz', ['course' => $course->id, 'name' => '合成测验', 'grade' => 100]);
$qg = $g->get_plugin_generator('core_question');
$qbank = $g->create_module('qbank', ['course' => $course->id, 'name' => '合成题库']);
$cat = $qg->create_question_category(['contextid' => context_module::instance($qbank->cmid)->id]);
$question = question_bank::get_qtype('shortanswer')->save_question((object)['qtype' => 'shortanswer'],
    (object)['category' => (string)$cat->id, 'name' => '合成加法',
        'questiontext' => ['text' => '1+1=?', 'format' => FORMAT_HTML],
        'generalfeedback' => ['text' => '', 'format' => FORMAT_HTML],
        'defaultmark' => 1, 'usecase' => 0, 'answer' => ['2'], 'fraction' => [1],
        'feedback' => [['text' => '合成正确答案', 'format' => FORMAT_HTML]],
        'status' => 'ready']);
quiz_add_quiz_question($question->id, $quiz);
\mod_quiz\quiz_settings::create($quiz->id)->get_grade_calculator()->recompute_quiz_sumgrades();
$qzgen = $g->get_plugin_generator('mod_quiz');
foreach ([$s1, $s2, $s3] as $p) {
    \core\session\manager::set_user($p);
    $attempt = $qzgen->create_attempt($quiz->id, $p->id);
    $attemptobj = \mod_quiz\quiz_attempt::create($attempt->id);
    $qa = $attemptobj->get_question_attempt(1);
    $attemptobj->process_submitted_actions(time(), false, [
        $qa->get_control_field_name('sequencecheck') => $qa->get_sequence_check_count(),
        $qa->get_qt_field_name('answer') => '2']);
    $attemptobj->process_submit(time(), false);
    $attemptobj->process_grade_submission(time());
}
\core\session\manager::set_user($teacher);
$assignments = [];
foreach ([false, true] as $team) {
    $module = $g->create_module('assign', ['course' => $course->id,
        'name' => $team ? '合成小组作业' : '合成个人作业（重开）',
        'assignsubmission_onlinetext_enabled' => 1, 'assignsubmission_file_enabled' => 0,
        'attemptreopenmethod' => 'manual', 'maxattempts' => 2,
        'teamsubmission' => (int)$team,
        ...($team ? ['teamsubmissiongroupingid' => 'SYNTH-GROUPING'] : []),
        'requireallteammemberssubmit' => 0, 'sendstudentnotifications' => 0]);
    $assignments[] = $module->id;
    $cm = get_coursemodule_from_id('assign', $module->cmid);
    $a = new assign(context_module::instance($cm->id), $cm, $course);
    for ($attemptno = 0; $attemptno < ($team ? 1 : 2); $attemptno++) {
        \core\session\manager::set_user($s1);
        $notices = [];
        $data = (object)['onlinetext_editor' => ['text' => '合成提交 ' . $attemptno,
            'format' => FORMAT_HTML, 'itemid' => 0]];
        $a->save_submission($data, $notices);
        $a->submit_for_grading((object)['userid' => $s1->id], $notices);
        \core\session\manager::set_user($teacher);
        $a->save_grade($s1->id, (object)['grade' => 60 + $attemptno * 10,
            'attemptnumber' => $attemptno, 'addattempt' => !$team && $attemptno == 0,
            'applytoall' => $team, 'sendstudentnotifications' => 0]);
    }
    $a->save_grade($s1->id, (object)['grade' => 85, 'attemptnumber' => $team ? 0 : 1,
        'addattempt' => 0, 'applytoall' => $team, 'sendstudentnotifications' => 0]);
}
$tx->allow_commit();
echo json_encode(['courses' => array_column($courses, 'id'), 'learners' => [$s1->id, $s2->id, $s3->id],
    'teacher' => $teacher->id, 'assignments' => $assignments, 'quiz' => $quiz->id,
    'resource' => $video->id, 'group' => $group->id, 'grouping' => $grouping->id], JSON_PRETTY_PRINT) . "\n";
