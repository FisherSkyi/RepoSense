FROM eclipse-temurin:11-jre

ARG REPOSENSE_JAR_URL=https://github.com/reposense/RepoSense/releases/latest/download/RepoSense.jar
ARG REPOSENSE_JAR_SHA256=

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && mkdir -p /opt/reposense \
    && curl -fL --retry 3 --retry-all-errors "$REPOSENSE_JAR_URL" -o /opt/reposense/RepoSense.jar \
    && if [ -n "$REPOSENSE_JAR_SHA256" ]; then echo "$REPOSENSE_JAR_SHA256  /opt/reposense/RepoSense.jar" | sha256sum -c -; fi \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

EXPOSE 9000

ENTRYPOINT ["java", "-jar", "/opt/reposense/RepoSense.jar"]
