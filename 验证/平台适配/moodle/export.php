<?php
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
require_once($CFG->dirroot . '/backup/util/includes/backup_includes.php');
\core\session\manager::set_user(get_admin());
$output = $argv[1];
if (!is_dir($output)) {
    throw new RuntimeException('Output directory missing');
}
function write_json($name, $value) {
    global $output;
    file_put_contents($output . '/' . $name . '.json', json_encode($value,
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n");
}
$tables = ['course', 'course_modules', 'resource', 'files', 'quiz', 'quiz_slots', 'quiz_attempts', 'quiz_grades',
    'question', 'question_versions', 'question_bank_entries', 'question_references', 'question_answers',
    'question_usages', 'question_attempts', 'question_attempt_steps', 'question_attempt_step_data',
    'assign', 'assign_submission', 'assignsubmission_onlinetext', 'assign_grades', 'assign_plugin_config',
    'grade_items', 'grade_grades', 'grade_grades_history', 'grade_items_history',
    'groups', 'groups_members', 'groupings', 'groupings_groups', 'user_enrolments', 'enrol',
    'role', 'role_assignments', 'context', 'logstore_standard_log'];
$omitted = [];
foreach ($tables as $table) {
    $columns = array_keys($DB->get_columns($table));
    $safe = array_values(array_filter($columns, fn($c) => !preg_match('/password|secret|token/i', $c)));
    $omitted[$table] = array_values(array_diff($columns, $safe));
    write_json($table, array_values($DB->get_records($table, null, 'id', implode(',', $safe))));
}
write_json('user', array_values($DB->get_records('user', null, 'id',
    'id,username,firstname,lastname,email,auth,suspended,deleted,idnumber')));
write_json('export_policy', ['omitted_sensitive_columns' => $omitted,
    'user_projection' => 'id,username,firstname,lastname,email,auth,suspended,deleted,idnumber',
    'scope' => 'All rows of the listed tables in an isolated synthetic-only site; no standard conversion']);
require($CFG->dirroot . '/version.php');
write_json('platform', ['release' => $release, 'version' => $version, 'php' => PHP_VERSION,
    'db' => $DB->get_field_sql('SELECT version()'),
    'commit' => '2d4bafe8548a6d6c01494c862ec3d9749ba6ea84',
    'evidence_level' => '真实平台数据（合成课程/学员）']);
$courseid = $DB->get_field('course', 'id', ['shortname' => 'SYNTH-OPEN-01'], MUST_EXIST);
$bc = new backup_controller(backup::TYPE_1COURSE, $courseid, backup::FORMAT_MOODLE,
    backup::INTERACTIVE_NO, backup::MODE_GENERAL, get_admin()->id);
$bc->get_plan()->get_setting('users')->set_value(false);
$bc->execute_plan();
$result = $bc->get_results();
$result['backup_destination']->copy_content_to($output . '/course-no-users.mbz');
$result['backup_destination']->delete();
$bc->destroy();
echo "Exported raw tables and no-user backup\n";
