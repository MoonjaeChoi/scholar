# Generated: 2025-10-07 13:45:00 KST
FROM python:3.11-slim

# Install system dependencies including Chromium and Oracle Client
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    libaio1t64 \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Chrome/ChromeDriver compatibility
RUN ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/bin/chromium /usr/bin/chrome \
    && ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver

# Install Oracle Instant Client
RUN mkdir -p /opt/oracle \
    && cd /opt/oracle \
    && wget https://download.oracle.com/otn_software/linux/instantclient/2115000/instantclient-basic-linux.x64-21.15.0.0.0dbru.zip \
    && unzip instantclient-basic-linux.x64-21.15.0.0.0dbru.zip \
    && rm instantclient-basic-linux.x64-21.15.0.0.0dbru.zip \
    && sh -c "echo /opt/oracle/instantclient_21_15 > /etc/ld.so.conf.d/oracle-instantclient.conf" \
    && ldconfig \
    && if [ -f /lib/x86_64-linux-gnu/libaio.so.1t64 ]; then ln -sf /lib/x86_64-linux-gnu/libaio.so.1t64 /lib/x86_64-linux-gnu/libaio.so.1; fi \
    && mkdir -p /opt/oracle/instantclient_21_15/lib \
    && ln -sf /opt/oracle/instantclient_21_15/*.so* /opt/oracle/instantclient_21_15/lib/

# Set Oracle environment variables
ENV ORACLE_HOME=/opt/oracle/instantclient_21_15
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_21_15:/opt/oracle/instantclient_21_15/lib

# Set working directory
WORKDIR /opt/scholar

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY training/ ./training/
COPY config/ ./config/

# Create data and log directories
RUN mkdir -p /opt/scholar/data /var/log/scholar

# Copy and set entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set Python path
ENV PYTHONPATH=/opt/scholar

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Use entrypoint to ensure LD_LIBRARY_PATH is set before Python starts
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command
CMD ["python", "src/main.py"]
