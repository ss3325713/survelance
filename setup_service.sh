#!/usr/bin/env bash
set -e

SERVICE_NAME="wheat-watch.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"

echo "=== Wheat Watch Linux Mint systemd User Service Setup ==="

mkdir -p "${USER_SYSTEMD_DIR}"
cp "wheat-watch.service" "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"

systemctl --user daemon-reload

echo "[✓] Service installed to: ${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
echo ""
echo "To start Wheat Watch now:"
echo "  systemctl --user start ${SERVICE_NAME}"
echo ""
echo "To enable Wheat Watch to start automatically at login:"
echo "  systemctl --user enable ${SERVICE_NAME}"
echo ""
echo "To check service status:"
echo "  systemctl --user status ${SERVICE_NAME}"
echo ""
echo "To stop Wheat Watch:"
echo "  systemctl --user stop ${SERVICE_NAME}"
