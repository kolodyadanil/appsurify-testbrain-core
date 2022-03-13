FROM python:3.9.9-slim-buster
MAINTAINER Artem Demidenko <ar.demidenko@gmail.com>

ENV DEBIAN_FRONTEND 'noninteractive'

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONIOENCODING 'utf-8'

ENV GIT_PYTHON_REFRESH 'quiet'
ENV GIT_DISCOVERY_ACROSS_FILESYSTEM 1

ENV PATH "/opt/app/bin:$PATH"
ENV DJANGO_STORAGE_ROOT '/opt/app/storage'

RUN mkdir -p /usr/share/man/man1

RUN echo "postfix postfix/mailname string localhost" | debconf-set-selections && \
    echo "postfix postfix/main_mailer_type string 'Internet Site'" | debconf-set-selections

RUN apt-get update -y && apt-get install -y \
    build-essential curl gnupg2 ca-certificates lsb-release \
    libpq-dev gettext wget gnupg p7zip-full openssh-server \
    ssh net-tools git gcc make software-properties-common \
    locales libcurl4-openssl-dev librtmp-dev libssl-dev default-jre \
    cron mailutils postfix postgresql-client \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false

# Requirements are installed here to ensure they will be cached.
RUN /usr/local/bin/python -m pip install --upgrade pip
COPY ./packages /tmp/packages
COPY ./requirements /tmp/requirements
RUN cd /tmp/requirements  \
    && pip install --no-cache-dir -r /tmp/requirements/build.txt \
    && rm -rf /tmp/requirements

RUN mkdir -p \
    /opt/app/bin \
    /opt/app/html \
    /opt/app/python \
    /opt/app/python/media \
    /opt/app/python/static \
    /opt/app/pids \
    /opt/app/logs \
    /opt/app/crons \
    ${DJANGO_STORAGE_ROOT}

COPY ./bin /opt/app/bin
RUN chmod -R +x /opt/app/bin
RUN ln -s /opt/app/bin/perforce/nix/p4 /opt/app/bin/p4

COPY ./compose/testbrain/core/notify/cron /opt/app/crons/cron-notify
COPY ./compose/testbrain/core/ml/cron /opt/app/crons/cron-ml

COPY ./compose/testbrain/core/docker-entrypoint /docker-entrypoint
RUN sed -i 's/\r$//g' /docker-entrypoint
RUN chmod +x /docker-entrypoint

COPY ./compose/testbrain/core/celery/worker/start /start-worker
RUN sed -i 's/\r$//g' /start-worker
RUN chmod +x /start-worker

COPY ./compose/testbrain/core/celery/beat/start /start-beat
RUN sed -i 's/\r$//g' /start-beat
RUN chmod +x /start-beat

COPY ./compose/testbrain/core/notify/start /start-notify
RUN sed -i 's/\r$//g' /start-notify
RUN chmod +x /start-notify

COPY ./compose/testbrain/core/ml/start /start-ml
RUN sed -i 's/\r$//g' /start-ml
RUN chmod +x /start-ml

COPY ./compose/testbrain/core/celery/flower/start /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

COPY ./compose/testbrain/core/api/start /start-api
RUN sed -i 's/\r$//g' /start-api
RUN chmod +x /start-api

COPY ./src /opt/app/python

WORKDIR /opt/app/python

ENTRYPOINT ["/docker-entrypoint"]
