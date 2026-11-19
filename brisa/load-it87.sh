#!/bin/bash
set -euo pipefail

# The startup script lives in /mnt/SSD/Containers/brisa.
# Keep using the previously built kernel-specific modules at their existing path.
base=/mnt/SSD/Containers/it8613e-fan-control
kernel_release="$(uname -r)"
module_path="$base/modules/$kernel_release/it87.ko"

controller_available() {
    for sensor in /sys/class/hwmon/hwmon*; do
        [ -f "$sensor/name" ] || continue
        if [[ "$(cat "$sensor/name")" == "it8613" &&
              -f "$sensor/pwm2" && -f "$sensor/pwm2_enable" &&
              -f "$sensor/fan2_input" ]]; then
            printf 'IT8613 fan controls available at %s\n' "$sensor"
            return 0
        fi
    done
    return 1
}

if controller_available; then
    exit 0
fi

if [ -d /sys/module/it87 ]; then
    printf 'An it87 module is loaded, but IT8613 PWM controls are unavailable.\n' >&2
    exit 1
fi

if [ ! -f "$module_path" ]; then
    printf 'Build an IT8613 module for kernel %s before loading it.\n' \
        "$kernel_release" >&2
    exit 1
fi

module_vermagic="$(modinfo -F vermagic "$module_path")"
if [[ "$module_vermagic" != "$kernel_release "* ]]; then
    printf 'Module kernel mismatch: %s\n' "$module_vermagic" >&2
    exit 1
fi

modprobe hwmon-vid
insmod "$module_path"
if ! controller_available; then
    printf 'Driver loaded, but the expected IT8613 fan controls are missing.\n' >&2
    exit 1
fi
printf 'Loaded IT8613 driver for kernel %s\n' "$kernel_release"
