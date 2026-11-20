#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .runtime
docker info > .runtime/docker-info.txt
# Stop at the first failing registry operation; do not retry shared limits.
docker pull moodlehq/moodle-php-apache:8.3 2>&1 | tee .runtime/php-pull.log
printf '%s\n' 'Image pull gate succeeded. Full deployment and seed remain unimplemented; see README.md.' >&2
exit 2
