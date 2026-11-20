#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .runtime
export PHP_IMAGE="${PHP_IMAGE:-${IMAGE_REGISTRY:-mirror.gcr.io}/moodlehq/moodle-php-apache:8.3@sha256:1db7b6ed013fcb5268095b5e28c410ba9117d38d9b6a324c100c48fcbe69745e}"
export DB_IMAGE="${DB_IMAGE:-${IMAGE_REGISTRY:-mirror.gcr.io}/library/postgres:17@sha256:b60e90042aa6b8dbecd58e224b3e36114dbf8ad754465264c2476ad58a86e45c}"
if [ ! -f .runtime/db.env ]; then
    umask 077
    printf 'POSTGRES_PASSWORD=%s\nPOSTGRES_USER=moodle\nPOSTGRES_DB=moodle\n' "$(openssl rand -hex 24)" > .runtime/db.env
fi
if [ ! -d .runtime/moodle-2d4bafe8548a6d6c01494c862ec3d9749ba6ea84 ]; then
    curl -fL https://codeload.github.com/moodle/moodle/tar.gz/2d4bafe8548a6d6c01494c862ec3d9749ba6ea84 -o .runtime/source.tar.gz
    tar -xzf .runtime/source.tar.gz -C .runtime
fi
cp config.php .runtime/moodle-2d4bafe8548a6d6c01494c862ec3d9749ba6ea84/config.php
docker compose up -d --wait
if ! docker compose exec -T db psql -U moodle -tAc "SELECT value FROM mdl_config WHERE name='version'" 2>/dev/null | rg -q '[0-9]'; then
    docker compose exec -T web php /var/www/html/admin/cli/install_database.php --agree-license --adminuser=syntheticadmin --adminpass="$(openssl rand -hex 24)Aa!" --adminemail=admin@example.invalid --fullname='Synthetic Moodle' --shortname=SYNTH --lang=en
fi
docker compose exec -T web php -r 'define("CLI_SCRIPT", true); require("/var/www/html/config.php"); echo "Installed Moodle ", $CFG->release, " / PHP ", PHP_VERSION, "\n";'
