#     poetry
#       |
#     [venv]
#       |
#       V
#     django              frontend
#         \                 /
#          \               /
#        [Django       [Frontend
#         static        static
#          files]       files]
#               \       /
#                 \   /
#                   V
#                 Nginx


FROM python:3.11-slim AS poetry

WORKDIR /home
ENV PATH $PATH:/root/.local/bin

RUN apt-get update && apt-get install -yqq \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python - \
    && poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi -vvv


FROM python:3.11-slim AS django

ENV PYTHONUNBUFFERED 1
ENV DEBUG False

RUN apt-get update && apt-get install -yqq \
    libpq-dev postgresql-client-15 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash 1000 \
    && mkdir /opt/django \
    && chown -R 1000:1000 /opt/django

COPY docker/django/ /opt/django/
RUN chmod -R +x /opt/django/

COPY --from=poetry --chown=1000:1000 /home/.venv /opt/django/.venv
ENV PATH /opt/django/.venv/bin:$PATH

USER 1000
RUN mkdir /opt/django/tracker
WORKDIR /opt/django/tracker
COPY --chown=1000:1000 tracker ./

RUN mkdir /opt/django/static \
    && python manage.py collectstatic --no-input

HEALTHCHECK CMD curl -f http://localhost/admin/ || exit 1
CMD /opt/django/entrypoint.sh


FROM nginx:stable AS nginx

ARG CERTBOT_EMAIL
ARG DOMAIN_LIST

RUN  apt-get update \
      && apt-get install -y cron certbot python-certbot-nginx bash wget \
      && certbot certonly --standalone --agree-tos -m "${CERTBOT_EMAIL}" -n -d ${DOMAIN_LIST} \
      && rm -rf /var/lib/apt/lists/* \
      && echo "PATH=$PATH" > /etc/cron.d/certbot-renew  \
      && echo "@monthly certbot renew --nginx >> /var/log/cron.log 2>&1" >> /etc/cron.d/certbot-renew \
      && crontab /etc/cron.d/certbot-renew

VOLUME /etc/letsencrypt

RUN mkdir -p /opt/nginx
COPY docker/nginx/ /etc/nginx/templates/
COPY --from=django /opt/django/static /opt/nginx/static

HEALTHCHECK CMD curl -f http://localhost/healthy || exit 1
CMD [ "sh", "-c", "cron && nginx -g 'daemon off;'" ]
