#!/bin/sh
# DemandRadar Postgres backup loop.
#
# Runs inside the `backup` sidecar (postgres:16-alpine). Every
# BACKUP_INTERVAL_HOURS hours dumps the DB into /backups/backup-<date>.sql.gz,
# rotates files older than BACKUP_KEEP_DAYS, and (when configured) uploads to
# the configured S3-compatible bucket.
#
# Required env:
#   POSTGRES_HOST / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
# Optional env:
#   BACKUP_INTERVAL_HOURS (default 24)
#   BACKUP_KEEP_DAYS      (default 14)
#   BACKUP_S3_BUCKET      (e.g. s3://my-bucket/demandradar)
#   BACKUP_S3_ENDPOINT    (e.g. https://s3.us-east-1.amazonaws.com)
#   BACKUP_S3_ACCESS_KEY  / BACKUP_S3_SECRET_KEY
set -eu

INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
HOST="${POSTGRES_HOST:-postgres}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-demandradar}"
DB="${POSTGRES_DB:-demandradar}"

mkdir -p /backups
echo "[backup] loop starting interval=${INTERVAL_HOURS}h keep=${KEEP_DAYS}d host=${HOST} db=${DB}"

# Optionally install awscli for S3 uploads. We avoid the heavy aws-cli image
# by pulling it on first run only when BACKUP_S3_BUCKET is set.
maybe_install_awscli() {
  if [ -n "${BACKUP_S3_BUCKET:-}" ] && ! command -v aws >/dev/null 2>&1; then
    apk add --no-cache aws-cli >/dev/null 2>&1 || \
      apk add --no-cache py3-pip >/dev/null && pip3 install --quiet awscli || true
  fi
}

run_once() {
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out="/backups/backup-${ts}.sql.gz"
  echo "[backup] dump -> ${out}"
  PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${HOST}" -p "${PORT}" -U "${USER}" -d "${DB}" --format=plain \
    | gzip > "${out}.tmp"
  mv "${out}.tmp" "${out}"

  if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    AWS_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY:-}" \
    AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_KEY:-}" \
      aws s3 cp "${out}" "${BACKUP_S3_BUCKET%/}/$(basename "${out}")" \
        ${BACKUP_S3_ENDPOINT:+--endpoint-url "${BACKUP_S3_ENDPOINT}"} \
        --only-show-errors || echo "[backup] s3 upload failed (kept local copy)"
  fi

  find /backups -type f -name 'backup-*.sql.gz' -mtime "+${KEEP_DAYS}" -print -delete \
    || true
  echo "[backup] done"
}

maybe_install_awscli || true

# Run once on startup so operators see the first dump immediately.
run_once || echo "[backup] initial run failed; will retry"

while :; do
  sleep "$((INTERVAL_HOURS * 3600))"
  run_once || echo "[backup] run failed; sleeping until next cycle"
done
