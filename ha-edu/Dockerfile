ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

# Install required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
