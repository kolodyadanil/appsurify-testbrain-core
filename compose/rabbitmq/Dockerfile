FROM rabbitmq:3.9.4-management-alpine

RUN echo "consumer_timeout = 172800000" >> /etc/rabbitmq/conf.d/20-consumer-timeout.conf

ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["rabbitmq-server"]
