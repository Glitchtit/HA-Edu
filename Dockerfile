FROM python:3.11-slim

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

# Create data directory
RUN mkdir -p /data

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run the application with Gunicorn
# --worker-class gevent enables WebSocket support via gevent
# Note: Removed --preload to allow gevent monkey-patching in wsgi.py to work correctly
# The wsgi.py module applies monkey-patching before importing app to avoid SSL import warnings
# Increased workers to 8 for better handling of concurrent requests with many instances
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "8", "--worker-class", "gevent", "--timeout", "120", "wsgi:application"]
