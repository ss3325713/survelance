#!/usr/bin/env bash
set -e

SERVICE_NAME="wheat-watch.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="${PROJECT_DIR}/.venv/bin/python"

if [ ! -f "${PYTHON_EXEC}" ]; then
    PYTHON_EXEC="$(which python3)"
fi

echo "=== PySURVEILLANCE Linux systemd User Service Setup ==="
echo "Project Directory: ${PROJECT_DIR}"
echo "Python Executable: ${PYTHON_EXEC}"

mkdir -p "${USER_SYSTEMD_DIR}"

cat <<EOF > "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
[Unit]
Description=PySURVEILLANCE Field & Facility Surveillance Service
After=network.target sound.target default.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_EXEC} ${PROJECT_DIR}/run.py
Restart=always
RestartSec=3
TimeoutStopSec=5
KillMode=mixed
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload

echo "[✓] Service generated and installed to: ${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
echo ""
echo "To start PySURVEILLANCE now:"
echo "  systemctl --user start ${SERVICE_NAME}"
echo ""
echo "To enable PySURVEILLANCE to start automatically at login:"
echo "  systemctl --user enable ${SERVICE_NAME}"
echo ""
echo "To check service status:"
echo "  systemctl --user status ${SERVICE_NAME}"
echo ""
echo "To stop PySURVEILLANCE:"
echo "  systemctl --user stop ${SERVICE_NAME}"
