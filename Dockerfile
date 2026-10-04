# syntax=docker/dockerfile:1
#
# The llms-txt-gen CLI as an image. Build and run with:
#   docker build -t llms-txt-gen .
#   docker run --rm -v "$PWD:/work" llms-txt-gen generate docs --out llms.txt
#
# The base image is pinned by digest (python:3.12-slim, multi-arch index).
ARG PYTHON_IMAGE=python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016

# Build the wheel in a throwaway stage so the build backend never reaches the runtime image.
FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY llms_txt_gen/ llms_txt_gen/
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM ${PYTHON_IMAGE}
ARG VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="llms-txt-gen" \
      org.opencontainers.image.description="Generate llms.txt for a docs site or repository from Markdown, HTML or a sitemap, and check existing files" \
      org.opencontainers.image.source="https://github.com/basitalisandhu/llms-txt-gen" \
      org.opencontainers.image.url="https://github.com/basitalisandhu/llms-txt-gen" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    pip install --no-deps /wheels/*.whl \
 && useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin app
# Mount the docs or repository at /work; relative paths, including --out, resolve from there.
WORKDIR /work
USER 1000:1000
ENTRYPOINT ["llms-txt-gen"]
CMD ["--help"]
