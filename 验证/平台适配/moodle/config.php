<?php
unset($CFG);
global $CFG;
$CFG = new stdClass();
$CFG->dbtype = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->dbhost = 'db';
$CFG->dbname = 'moodle';
$CFG->dbuser = 'moodle';
$CFG->dbpass = getenv('POSTGRES_PASSWORD');
$CFG->prefix = 'mdl_';
$CFG->wwwroot = 'http://localhost:8087';
$CFG->dataroot = '/var/moodledata';
$CFG->admin = 'admin';
$CFG->directorypermissions = 0777;
$CFG->passwordpolicy = 0;
$CFG->noemailever = true;
$CFG->includeuserpasswordsinbackup = false;
require_once(__DIR__ . '/public/lib/setup.php');
