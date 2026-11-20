#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
mkdir -p .runtime
chmod 700 .runtime
if [[ ! -x .runtime/venv/bin/tutor ]]; then
    python3 -m venv .runtime/venv
    .runtime/venv/bin/pip install \
        'git+https://github.com/overhangio/tutor.git@e29ec3e0a9d66131fffb21bef5adc00ac799d712' \
        > .runtime/tutor-install.log 2>&1
fi
docker build --provenance=false -f image.Dockerfile -t wp4a-openedx:bae21257 . > .runtime/image-build.log 2>&1
local_image=$(docker image inspect --format '{{index .RepoDigests 0}}' wp4a-openedx:bae21257)
registry="${IMAGE_REGISTRY:-mirror.gcr.io}"
bash tutor.sh config save \
    --set 'PLUGINS=[]' \
    --set LMS_HOST=local.openedx.io \
    --set CMS_HOST=studio.local.openedx.io \
    --set ENABLE_HTTPS=false \
    --set LOCAL_PROJECT_NAME=wp4a_openedx \
    --set "DOCKER_IMAGE_OPENEDX=$local_image" \
    --set 'DOCKER_IMAGE_PERMISSIONS=overhangio/openedx-permissions:23.0.0-main@sha256:b2ed70fb930b09bf96a2e587a1271106d5649ef51f8f4fe688f45b6450370326' \
    --set "DOCKER_IMAGE_MYSQL=$registry/library/mysql:8.4@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902" \
    --set "DOCKER_IMAGE_MONGODB=$registry/library/mongo:7.0@sha256:884c055bff8b7144ca44830d01826facd3083b33c4dea44b94a1476c62de3c32" \
    --set "DOCKER_IMAGE_REDIS=$registry/library/redis:7.4@sha256:2e3eb11462c4e3759e6972678dd051d150ff54b1e60714b3c33b701260172a90" \
    --set "DOCKER_IMAGE_CADDY=$registry/library/caddy:2.11@sha256:4851e54a46b206517c574821bb5cc67f170d2156041e9fbc4c9193b45e84a75b" \
    --set RUN_MEILISEARCH=true \
    --set 'DOCKER_IMAGE_MEILISEARCH=getmeili/meilisearch:v1.36.0@sha256:203a0854738be101bfdada825ac3cbf95e5681bc849757b6bc199e4cfae98faa' \
    --set RUN_SMTP=false \
    --set OPENEDX_LMS_GRANIAN_WORKERS=2 \
    --set OPENEDX_CMS_GRANIAN_WORKERS=1
bash tutor.sh local launch -I --skip-build > .runtime/launch.log 2>&1
printf '%s\n' 'Tutor launch completed; private logs are in .runtime/.'
