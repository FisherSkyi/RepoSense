FROM eclipse-temurin:11-jre

ARG REPOSENSE_JAR_URL=https://github.com/reposense/RepoSense/releases/latest/download/RepoSense.jar
ARG REPOSENSE_JAR_SHA256=

# Install Python 3 + git (git is needed by RepoSense to clone repos)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git python3 \
    # Place the JAR where frontend_server.py expects it: build/jar/RepoSense.jar
    && mkdir -p /opt/reposense/build/jar \
    && curl -fL --retry 3 --retry-all-errors "$REPOSENSE_JAR_URL" \
         -o /opt/reposense/build/jar/RepoSense.jar \
    && if [ -n "$REPOSENSE_JAR_SHA256" ]; then \
         echo "$REPOSENSE_JAR_SHA256  /opt/reposense/build/jar/RepoSense.jar" | sha256sum -c -; \
       fi \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the frontend server script
COPY frontend_server.py /opt/reposense/frontend_server.py

# Reports are written to /opt/reposense/reposense-report
WORKDIR /opt/reposense

EXPOSE 9000

ENTRYPOINT ["python3", "/opt/reposense/frontend_server.py"]
