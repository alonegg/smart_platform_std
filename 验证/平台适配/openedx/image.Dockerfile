FROM overhangio/openedx:23.0.0-main@sha256:4c02292ee576964472f92be4b8b78972202af2dde57d095114d1fea13ad99a2f
RUN pip install setuptools==80.9.0 apache-libcloud==3.9.1 fasteners==0.20 \
    'git+https://github.com/openedx/event-routing-backends.git@bae21257a259d17d54d9501af0abdd0c8e002ed8'
