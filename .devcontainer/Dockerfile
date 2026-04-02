# ベースイメージ
FROM mcr.microsoft.com/devcontainers/python:3.12

# 非対話モード
ENV DEBIAN_FRONTEND=noninteractive

# 基本ツール
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	ca-certificates \
	curl \
	git \
	gnupg \
	unzip \
	&& rm -rf /var/lib/apt/lists/*

# Terraform
RUN curl -fsSL https://apt.releases.hashicorp.com/gpg \
	| gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
	&& . /etc/os-release \
	&& echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com ${VERSION_CODENAME} main" \
	> /etc/apt/sources.list.d/hashicorp.list \
	&& apt-get update \
	&& apt-get install -y --no-install-recommends terraform \
	&& rm -rf /var/lib/apt/lists/*

# Google Cloud CLI
RUN curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
	| gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
	&& echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
	> /etc/apt/sources.list.d/google-cloud-sdk.list \
	&& apt-get update \
	&& apt-get install -y --no-install-recommends google-cloud-cli \
	&& rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY requirements.txt /tmp/pip-tmp/

# Install python dependencies from requirements.txt
RUN pip install --no-cache-dir -r /tmp/pip-tmp/requirements.txt

# Clean up the temporary directory
RUN rm -rf /tmp/pip-tmp
