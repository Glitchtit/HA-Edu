ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

# Fallback: install Python3/pip via apk if the HA Alpine base image is used
# (happens when HA Supervisor resets build.yaml and falls back to its default base)
RUN if ! command -v pip3 >/dev/null 2>&1 && ! command -v pip >/dev/null 2>&1; then \
      apk add --no-cache python3 py3-pip; \
    fi

# Install required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY wsgi.py .
COPY app.py .
COPY interaction_logger.py .
COPY templates/ templates/
COPY master_configuration.yaml .

# Copy entrypoint
COPY run.sh /
RUN chmod a+x /run.sh

# Create data directory
RUN mkdir -p /data

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

CMD [ "/run.sh" ]
