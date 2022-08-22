# Dockerfile for RabbitMQ worker
#
FROM rabbitmq:3-alpine
LABEL maintainer="IETF Tools Team <tools-discuss@ietf.org>"

# Copy the startup file
COPY dev/mq/ietf-rabbitmq-server.bash /ietf-rabbitmq-server.bash
RUN sed -i 's/\r$//' /ietf-rabbitmq-server.bash && \
    chmod +x /ietf-rabbitmq-server.bash

# Put the rabbitmq.conf in the conf.d so it runs after 10-defaults.conf.
# Can override this for an individual container by mounting additional
# config files in /etc/rabbitmq/conf.d.
COPY dev/mq/rabbitmq.conf /etc/rabbitmq/conf.d/20-ietf-config.conf
COPY dev/mq/definitions.json /definitions.json

CMD ["/ietf-rabbitmq-server.bash"]
