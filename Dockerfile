FROM eclipse-temurin:11-jre

ARG REPOSENSE_JAR_URL=https://github.com/reposense/RepoSense/releases/latest/download/RepoSense.jar

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && mkdir -p /opt/reposense \
    && curl -fL "$REPOSENSE_JAR_URL" -o /opt/reposense/RepoSense.jar \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENTRYPOINT ["java", "-jar", "/opt/reposense/RepoSense.jar"]
