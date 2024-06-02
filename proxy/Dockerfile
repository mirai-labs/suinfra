FROM haproxy:latest

WORKDIR /app

COPY ./haproxy.cfg /etc/haproxy/haproxy.cfg
COPY ./start.sh ./start.sh
COPY ./region_configs ./region_configs

# Start HAProxy
CMD ["bash", "/app/start.sh"]