# Maven Builder Docker Image for TestBoost
# Provides a consistent build environment for Maven projects

ARG JAVA_VERSION=17
ARG MAVEN_VERSION=3.9.5

FROM maven:${MAVEN_VERSION}-eclipse-temurin-${JAVA_VERSION}

LABEL maintainer="TestBoost Team"
LABEL description="Maven build environment for TestBoost"
LABEL version="1.0.0"

# Install additional tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set up Maven settings directory
RUN mkdir -p /root/.m2

# Copy custom Maven settings if needed
# COPY settings.xml /root/.m2/settings.xml

# Set up working directory
WORKDIR /project

# Create volume mount points
VOLUME ["/project", "/root/.m2"]

# Environment variables
ENV MAVEN_OPTS="-Xmx2g -XX:+UseG1GC"
ENV JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD mvn --version || exit 1

# Default command - keeps container running
CMD ["tail", "-f", "/dev/null"]

# Alternative commands for specific tasks:
# Build: docker run --rm -v $(pwd):/project testboost/maven-builder mvn clean install
# Test: docker run --rm -v $(pwd):/project testboost/maven-builder mvn test
# Package: docker run --rm -v $(pwd):/project testboost/maven-builder mvn package -DskipTests
