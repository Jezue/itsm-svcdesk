#!/bin/sh
# ai-generated: 100% - OpenAI Codex wrote and ran the routing smoke checks.
set -eu
cd "$(dirname "$0")/.."
image=ghcr.io/swasik/itsmlab:2026
docker run --rm --entrypoint amtool -v "$PWD:/work:ro" "$image" \
  check-config /work/alertmanager/alertmanager.yml
for service in svcdesk frontend; do
  for severity in P1 P2 P3; do
    receiver=chat
    if [ "$severity" = P1 ]; then receiver=pager; fi
    docker run --rm --entrypoint amtool -v "$PWD:/work:ro" "$image" \
      config routes test --config.file=/work/alertmanager/alertmanager.yml \
      --verify.receivers="$receiver" "service=$service" "severity=$severity"
  done
done
