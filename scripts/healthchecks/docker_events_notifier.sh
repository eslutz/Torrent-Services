#!/bin/sh
# Listen to Docker container events and send email alerts for unhealthy/stop events

set -eu

export SERVICE_NAME=health-monitor
SCRIPT_DIR="$(dirname "$0")"
LOG_PATH=${LOG_PATH:-/logs/health-monitor/events.log}
mkdir -p "$(dirname "$LOG_PATH")" 2>/dev/null || true

. "$SCRIPT_DIR/healthcheck_utils.sh"

AUTOHEAL_LOG=${AUTOHEAL_LOG:-/logs/autoheal/log.json}

log_line() {
  MESSAGE="$1"
  echo "$(date -Iseconds) ${MESSAGE}" | tee -a "$LOG_PATH"
}

handle_event() {
  RAW="$1"
  ACTION=$(echo "$RAW" | jq -r '.Action // .status // ""')
  NAME=$(echo "$RAW" | jq -r '.Actor.Attributes.name // "unknown"')
  IMAGE=$(echo "$RAW" | jq -r '.Actor.Attributes.image // "unknown"')
  HEALTH=$(echo "$RAW" | jq -r '.Actor.Attributes.health_status // ""')

  case "$ACTION" in
    health_status)
      if [ "$HEALTH" = "unhealthy" ]; then
        log_line "Container unhealthy: ${NAME} (image: ${IMAGE})"
        send_email "Container unhealthy: ${NAME}" "The container ${NAME} is reporting UNHEALTHY (image: ${IMAGE})."
      fi
      ;;
    die|oom|kill|stop)
      log_line "Container ${ACTION}: ${NAME} (image: ${IMAGE})"
      send_email "Container ${ACTION}: ${NAME}" "The container ${NAME} reported event ${ACTION} (image: ${IMAGE})."
      ;;
  esac
}

follow_autoheal_log() {
  if [ ! -f "$AUTOHEAL_LOG" ]; then
    log_line "Autoheal log not found at $AUTOHEAL_LOG; skipping autoheal notifications"
    return
  fi

  log_line "Starting autoheal log watcher at $AUTOHEAL_LOG"
  tail -n 0 -F "$AUTOHEAL_LOG" | while read -r LINE; do
    [ -z "$LINE" ] && continue
    if ! echo "$LINE" | jq -e . >/dev/null 2>&1; then
      log_line "Autoheal log line not JSON: $LINE"
      continue
    fi
    ACTION=$(echo "$LINE" | jq -r '.action // ""')
    NAME=$(echo "$LINE" | jq -r '.name // "unknown"')
    CODE=$(echo "$LINE" | jq -r '.code // ""')
    ERR=$(echo "$LINE" | jq -r '.err // ""')

    if echo "$ACTION" | grep -qi "restart"; then
      log_line "Autoheal restart detected for ${NAME}: ${ACTION} (code=${CODE}, err=${ERR})"
      BODY="Autoheal restarted container ${NAME}.\nAction: ${ACTION}\nCode: ${CODE}\nError: ${ERR}"
      send_email "Autoheal restart: ${NAME}" "$BODY"
    fi
  done
}

if ! command -v docker >/dev/null 2>&1; then
  log_line "docker CLI not found inside container; cannot listen for events"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  log_line "jq not found inside container; cannot parse docker events"
  exit 1
fi

log_line "Starting docker event notifier (watching stop/die/kill/oom/unhealthy)"
follow_autoheal_log &

while true; do
  docker events \
    --format '{{json .}}' \
    --filter 'type=container' \
    --filter 'event=health_status' \
    --filter 'event=die' \
    --filter 'event=stop' \
    --filter 'event=kill' \
    --filter 'event=oom' | while read -r RAW_EVENT; do
      [ -z "$RAW_EVENT" ] && continue
      handle_event "$RAW_EVENT"
    done

  log_line "docker events stream ended; restarting in 5s"
  sleep 5
done
