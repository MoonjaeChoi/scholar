#!/bin/bash
# Generated: 2025-10-12 19:55:00 KST
# Entrypoint script for Scholar crawler container

set -e

# Ensure Oracle Client libraries are in the library path
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_15:/opt/oracle/instantclient_21_15/lib:${LD_LIBRARY_PATH}
ldconfig 2>/dev/null || true

# Execute the command passed to the container
exec "$@"
