# ---- Recipe for the container image ----
FROM python:3.11-slim

# N_THREADS must equal the number of vCPUs you give the container (Cloud Run: --cpu 4)
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    N_THREADS=4 \
    PORT=8080

# libgomp1 = OpenMP runtime used by llama.cpp (missing from the slim image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages first so Docker can cache this layer.
# Uses a prebuilt CPU wheel of llama-cpp-python: no compiling, and it is built
# for generic CPUs (avoids "illegal instruction" crashes on other machines).
# If this step fails with "no matching distribution", remove --only-binary and
# add build-essential + cmake to the apt-get line above (build takes ~10 min).
COPY requirements.txt .
RUN pip install --only-binary llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
    -r requirements.txt

# Model first (big, rarely changes), code last (changes often) -> faster rebuilds
COPY models/ ./models/
COPY app.py .

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
