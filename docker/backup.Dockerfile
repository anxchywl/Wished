FROM postgres:16-alpine

ARG TARGETARCH=amd64

RUN apk add --no-cache bash curl ca-certificates

RUN ARCH="${TARGETARCH:-amd64}" && \
    curl -sSL "https://dl.min.io/client/mc/release/linux-${ARCH}/mc" \
    -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

COPY infra/backup/entrypoint.sh /usr/local/bin/entrypoint
COPY infra/backup/backup.sh /usr/local/bin/backup
COPY infra/backup/restore.sh /usr/local/bin/restore
COPY infra/backup/verify.sh /usr/local/bin/verify-backup

RUN chmod +x \
    /usr/local/bin/entrypoint \
    /usr/local/bin/backup \
    /usr/local/bin/restore \
    /usr/local/bin/verify-backup

RUN mkdir -p /backups

VOLUME ["/backups"]

ENTRYPOINT ["/usr/local/bin/entrypoint"]
