#!/bin/sh
set -eu
exec python -m paperclip_notifier.cli --config "${PAPERCLIP_CONFIG:-/config/config.yaml}" check-config
