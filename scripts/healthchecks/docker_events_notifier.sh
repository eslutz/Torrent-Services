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
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') ${MESSAGE}" | tee -a "$LOG_PATH"
}

handle_event() {
  RAW="$1"
  ACTION=$(echo "$RAW" | jq -r '.Action // .status // ""')
  NAME=$(echo "$RAW" | jq -r '.Actor.Attributes.name // "unknown"')
  IMAGE=$(echo "$RAW" | jq -r '.Actor.Attributes.image // "unknown"')
  HEALTH=$(echo "$RAW" | jq -r '.Actor.Attributes.health_status // ""')
  EXIT_CODE=$(echo "$RAW" | jq -r '.Actor.Attributes.exitCode // ""')
  SIGNAL=$(echo "$RAW" | jq -r '.Actor.Attributes.signal // ""')

  case "$ACTION" in
    health_status)
      if [ "$HEALTH" = "unhealthy" ]; then
        log_line "Container unhealthy: ${NAME} (image: ${IMAGE})"
        send_notification "Container unhealthy: ${NAME}" "The container ${NAME} is reporting UNHEALTHY (image: ${IMAGE})."
      fi
      ;;
    die)
      # Only notify for abnormal exits (non-zero exit codes except 143)
      if [ -n "$EXIT_CODE" ] && [ "$EXIT_CODE" != "0" ] && [ "$EXIT_CODE" != "143" ]; then
        log_line "Container died abnormally: ${NAME} (image: ${IMAGE}, exitCode: ${EXIT_CODE})"

        # Get health check details if available
        HEALTH_INFO=$(docker inspect "${NAME}" --format '{{json .State.Health}}' 2>/dev/null || echo '{}')
        HEALTH_STATUS=$(echo "$HEALTH_INFO" | jq -r '.Status // "unknown"')
        LAST_OUTPUT=$(echo "$HEALTH_INFO" | jq -r '.Log[-1].Output // "No output available"' 2>/dev/null | head -c 500)
        LAST_EXIT=$(echo "$HEALTH_INFO" | jq -r '.Log[-1].ExitCode // "unknown"' 2>/dev/null)

        BODY="Container: ${NAME}\nImage: ${IMAGE}\nExit Code: ${EXIT_CODE}\n\nHealth Status: ${HEALTH_STATUS}\nLast Health Check Exit Code: ${LAST_EXIT}\n\nLast Health Check Output:\n${LAST_OUTPUT}\n\nPossible Causes:\n- Exit 137: Force killed (SIGKILL) after exceeding stop_grace_period\n- Exit 1: Application error or failed startup\n- Check container logs: docker logs ${NAME}"
        send_notification "Container died: ${NAME}" "$BODY"
      else
        log_line "Container stopped normally: ${NAME} (image: ${IMAGE}, exitCode: ${EXIT_CODE})"
      fi
      ;;
    oom)
      log_line "Container OOM: ${NAME} (image: ${IMAGE})"
      send_notification "Container OOM: ${NAME}" "The container ${NAME} ran out of memory (image: ${IMAGE})."
      ;;
    kill)
      # Only notify for force kills (SIGKILL/signal 9), not normal SIGTERM
      if [ -n "$SIGNAL" ] && [ "$SIGNAL" != "15" ]; then
        log_line "Container force killed: ${NAME} (image: ${IMAGE}, signal: ${SIGNAL})"

        # Get grace period info
        GRACE_PERIOD=$(docker inspect "${NAME}" --format '{{.HostConfig.StopTimeout}}' 2>/dev/null || echo "unknown")

        BODY="Container: ${NAME}\nImage: ${IMAGE}\nSignal: ${SIGNAL} (SIGKILL - force kill)\nGrace Period: ${GRACE_PERIOD}s\n\nCause: Container did not stop within grace period after receiving SIGTERM (signal 15).\nDocker sent SIGKILL to forcefully terminate the process.\n\nPossible Reasons:\n- Application not handling SIGTERM properly\n- Long-running operations (downloads, database transactions)\n- Insufficient grace period for clean shutdown\n- Hung process\n\nNext Steps:\n- Check container logs: docker logs ${NAME}\n- Consider increasing stop_grace_period in docker-compose.yml\n- Verify application handles SIGTERM signal"
        send_notification "Container force killed: ${NAME}" "$BODY"
      else
        log_line "Container received shutdown signal: ${NAME} (image: ${IMAGE}, signal: ${SIGNAL})"
      fi
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

      # Get health check configuration
      HEALTH_CONFIG=$(docker inspect "${NAME}" --format '{{json .Config.Healthcheck}}' 2>/dev/null || echo '{}')
      HC_INTERVAL=$(echo "$HEALTH_CONFIG" | jq -r '.Interval // "unknown"')
      HC_TIMEOUT=$(echo "$HEALTH_CONFIG" | jq -r '.Timeout // "unknown"')
      HC_RETRIES=$(echo "$HEALTH_CONFIG" | jq -r '.Retries // "unknown"')
      HC_START=$(echo "$HEALTH_CONFIG" | jq -r '.StartPeriod // "unknown"')

      # Determine root cause
      CAUSE="Unknown"
      if echo "$ERR" | grep -q "timed out"; then
        CAUSE="Health check exceeded timeout (${HC_TIMEOUT}). The health check command did not complete in time."
      elif echo "$ERR" | grep -q "unhealthy"; then
        CAUSE="Health check failed ${HC_RETRIES} consecutive times. The service is not responding correctly."
      fi

      BODY="Container: ${NAME}\nAction: ${ACTION}\nAutoheal Code: ${CODE}\nError: ${ERR}\n\nHealth Check Configuration:\n- Interval: ${HC_INTERVAL}\n- Timeout: ${HC_TIMEOUT}\n- Retries: ${HC_RETRIES}\n- Start Period: ${HC_START}\n\nRoot Cause:\n${CAUSE}\n\nNext Steps:\n1. Check container logs: docker logs ${NAME}\n2. Review health check script output\n3. Consider increasing health check timeout if operations are slow\n4. Verify service is not overloaded or hanging\n5. Check if dependencies (VPN, network, databases) are healthy"
      send_notification "Autoheal restart: ${NAME}" "$BODY"
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

log_line "Starting docker event notifier (watching die/kill/oom/unhealthy)"
log_line "Notifications will be sent via email"
follow_autoheal_log &

while true; do
  docker events \
    --format '{{json .}}' \
    --filter 'type=container' \
    --filter 'event=health_status' \
    --filter 'event=die' \
    --filter 'event=kill' \
    --filter 'event=oom' | while read -r RAW_EVENT; do
      [ -z "$RAW_EVENT" ] && continue
      handle_event "$RAW_EVENT"
    done

  log_line "docker events stream ended; restarting in 5s"
  sleep 5
done
