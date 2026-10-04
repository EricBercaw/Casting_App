#!/usr/bin/env bash
set -euo pipefail

DEVICE_NAME="Living Room Audio"

echo "== Starting Bluetooth service =="
sudo systemctl enable --now bluetooth
bluetoothctl power on >/dev/null || true

echo "== Scanning for ${DEVICE_NAME} for 15 seconds =="
bluetoothctl --timeout 15 scan on || true

MAC="$({ bluetoothctl devices 2>/dev/null || true; } | awk -v name="$DEVICE_NAME" '
BEGIN { IGNORECASE=1 }
$1 == "Device" {
    line=$0
    sub(/^Device[[:space:]]+[0-9A-Fa-f:]+[[:space:]]+/, "", line)
    if (tolower(line) == tolower(name)) {
        print $2
        exit
    }
}')"

if [[ -z "$MAC" ]]; then
    echo
    echo "ERROR: ${DEVICE_NAME} was not found."
    echo "Make sure the ESP32-A1S is powered, running the Bluetooth receiver firmware,"
    echo "and visible as '${DEVICE_NAME}', then run this script again."
    exit 1
fi

echo "Found ${DEVICE_NAME}: ${MAC}"

echo "== Pairing / trusting / connecting =="
bluetoothctl pair "$MAC" || true
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC" || true

INFO="$(bluetoothctl info "$MAC" || true)"
if ! grep -q "Connected: yes" <<<"$INFO"; then
    echo
    echo "ERROR: Device was found but is not connected."
    echo "$INFO"
    exit 1
fi

echo "== Waiting for A2DP audio sink =="
MAC_PIPEWIRE="${MAC//:/_}"
SINK=""

for _ in $(seq 1 20); do
    SINK="$(pactl list short sinks 2>/dev/null | awk -v mac="$MAC_PIPEWIRE" '
        tolower($2) ~ tolower(mac) && tolower($2) ~ /bluez/ { print $2; exit }
    ')"

    if [[ -n "$SINK" ]]; then
        break
    fi

    sleep 0.5
done

if [[ -z "$SINK" ]]; then
    echo
    echo "ERROR: Bluetooth connected, but no bluez audio sink appeared."
    echo "Current sinks:"
    pactl list short sinks || true
    exit 1
fi

echo "Audio sink: $SINK"
pactl set-default-sink "$SINK"

while read -r INPUT_ID _; do
    [[ -n "${INPUT_ID:-}" ]] || continue
    pactl move-sink-input "$INPUT_ID" "$SINK" || true
done < <(pactl list short sink-inputs)

echo
echo "== Success =="
echo "Bluetooth device: ${DEVICE_NAME}"
echo "MAC:              ${MAC}"
echo "Default sink:     $(pactl get-default-sink)"
echo
echo "Your computer audio now goes to ${DEVICE_NAME}."
echo "The casting app should send video only to the Apple TV."
