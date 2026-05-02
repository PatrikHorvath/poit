FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG DEV_PASSWORD

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    openssh-server \
    sudo \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir \
    flask \
    flask-socketio \
    eventlet \
    mysql-connector-python \
    cryptography \
    configparser

# SSH Setup
RUN mkdir /var/run/sshd
RUN useradd -m -s /bin/bash devuser && \
    echo "devuser:${DEV_PASSWORD}" | chpasswd && \
    adduser devuser sudo

# GIT Setup
RUN git config --global --add safe.directory /home/devuser && \
    cd /home/devuser && \
    git init -b main && \
    git remote add origin https://github.com/PatrikHorvath/poit && \
    echo "*" > .gitignore && \
    echo "!flask" >> .gitignore && \
    echo "!flask/**" >> .gitignore

RUN chown -R devuser:devuser /app /home/devuser

EXPOSE 22 5000
CMD ["/usr/sbin/sshd", "-D"]