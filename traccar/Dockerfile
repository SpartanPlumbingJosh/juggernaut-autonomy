FROM traccar/traccar:latest

# Copy custom config
COPY traccar.xml /opt/traccar/conf/traccar.xml

# Create data directory
RUN mkdir -p /opt/traccar/data /opt/traccar/logs

# Expose web UI and Teltonika protocol port
EXPOSE 8082 5027
