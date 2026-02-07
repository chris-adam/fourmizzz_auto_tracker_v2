FROM python:3.11-slim AS builder

WORKDIR /home
ENV PATH $PATH:/root/.local/bin

RUN apt-get update && apt-get install -yqq \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

COPY discord/pyproject.toml discord/uv.lock discord/README.md ./
RUN uv sync


FROM python:3.11-slim AS discord

RUN apt-get update && apt-get install -yqq \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash --badname 1000 \
    && mkdir /opt/discord \
    && chown -R 1000:1000 /opt/discord

COPY discord/main.py /opt/discord/
RUN chmod +x /opt/discord/main.py

COPY --from=builder --chown=1000:1000 /home/.venv /opt/discord/.venv
ENV PATH /opt/discord/.venv/bin:$PATH

USER 1000
WORKDIR /opt/discord

CMD [ "python", "main.py" ]
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health
