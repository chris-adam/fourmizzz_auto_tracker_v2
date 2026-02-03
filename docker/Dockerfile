#     builder
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


FROM python:3.11-slim AS builder

WORKDIR /home
ENV PATH $PATH:/root/.local/bin

RUN apt-get update && apt-get install -yqq \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock README.md ./
RUN uv sync


FROM python:3.11-slim AS django

ENV PYTHONUNBUFFERED 1
ENV DEBUG True

RUN apt-get update && apt-get install -yqq \
    libpq-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash --badname 1000 \
    && mkdir /opt/django \
    && chown -R 1000:1000 /opt/django

COPY docker/django/ /opt/django/
RUN chmod -R +x /opt/django/

COPY --from=builder --chown=1000:1000 /home/.venv /opt/django/.venv
ENV PATH /opt/django/.venv/bin:$PATH

USER 1000
RUN mkdir /opt/django/tracker
WORKDIR /opt/django/tracker
COPY --chown=1000:1000 tracker ./

RUN mkdir /opt/django/static \
    && python manage.py collectstatic --no-input

CMD /opt/django/entrypoint.sh


FROM nginx:stable AS nginx

RUN mkdir -p /opt/nginx
COPY docker/nginx/ /etc/nginx/conf.d/
COPY --from=django /opt/django/static /opt/nginx/static

HEALTHCHECK CMD curl -f http://localhost:8080/healthy || exit 1
