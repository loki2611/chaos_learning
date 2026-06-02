FROM python:3.12-slim
 
# ── System dependencies ───────────────────────────────────────────────────────
# curl  — used to download kubectl and verify connectivity
# openjdk-17-jre-headless — JMeter requires Java
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        curl \
        ca-certificates \
        default-jre \
    && rm -rf /var/lib/apt/lists/*
 
# ── kubectl ───────────────────────────────────────────────────────────────────
# Download the same version as your cluster (1.29 matches kind demo-cluster)
RUN curl -LO "https://dl.k8s.io/release/v1.29.0/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/kubectl
 
# ── JMeter ───────────────────────────────────────────────────────────────────
ENV JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/jmeter
RUN curl -L "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz" \
        -o /tmp/jmeter.tgz \
    && tar -xzf /tmp/jmeter.tgz -C /opt/ \
    && mv /opt/apache-jmeter-${JMETER_VERSION} ${JMETER_HOME} \
    && rm /tmp/jmeter.tgz
ENV PATH="${JMETER_HOME}/bin:${PATH}"
 
# ── Python packages ───────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# ── Application code ──────────────────────────────────────────────────────────
COPY . .
 
# ── Security: non-root user ───────────────────────────────────────────────────
# The user needs a home directory so kubectl can write its cache
RUN addgroup --system chaosgroup \
 && adduser  --system --ingroup chaosgroup --home /home/chaosuser chaosuser \
 && chown -R chaosuser:chaosgroup /app
USER chaosuser
 
# ── Ports & health ────────────────────────────────────────────────────────────
EXPOSE 8090
 
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8090/ || exit 1
 
# ── Start ─────────────────────────────────────────────────────────────────────
# Use gunicorn with threaded workers — SSE requires threads, not async
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8090", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "300", \
     "run:app"]