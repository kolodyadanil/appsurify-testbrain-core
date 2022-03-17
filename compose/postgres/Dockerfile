FROM postgres:10.6

COPY ./compose/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance
COPY ./compose/postgres/configuration/postgresql.conf /tmp/postgresql.conf
COPY ./compose/postgres/docker-entrypoint-initdb.d/updateConfig.sh /docker-entrypoint-initdb.d/updateConfig.sh
RUN chmod +x /docker-entrypoint-initdb.d/updateConfig.sh
