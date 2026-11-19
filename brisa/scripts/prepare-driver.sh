#!/bin/bash
# Prepare the tested IT8613E driver and loader; register startup in the portal.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    printf 'Run this installer as root using sudo bash.\n' >&2
    exit 1
fi
if ! mountpoint -q /mnt/SSD; then
    printf 'The SSD pool must be mounted at /mnt/SSD before installation.\n' >&2
    exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source_loader="$script_dir/../load-it87.sh"
bash -n "$source_loader"

base=/mnt/SSD/Containers/it8613e-fan-control
loader_dir=/mnt/SSD/Containers/brisa
kernel_release="$(uname -r)"
source_module="${1:-/tmp/it87-test.JpM0cX/driver/it87.ko}"
expected_sha256=a8bd152f7d7444f90a18efd76b5bccf745d936c67fa61d785af792fe0f7ae956
if ! printf '%s  %s\n' "$expected_sha256" "$source_module" | sha256sum --check --status; then
    printf 'Source module is missing or differs from the tested artifact.\n' >&2
    exit 1
fi
destination="$base/modules/$kernel_release"

module_vermagic="$(modinfo -F vermagic "$source_module")"
if [[ "$module_vermagic" != "$kernel_release "* ]]; then
    printf 'Module does not match the running kernel: %s\n' "$module_vermagic"
    exit 1
fi

install -d -m 0750 "$base" "$base/modules" "$destination" "$loader_dir"
install -m 0644 "$source_module" "$destination/it87.ko"

install -m 0750 "$source_loader" "$loader_dir/load-it87.sh"

bash -n "$loader_dir/load-it87.sh"
bash "$loader_dir/load-it87.sh"

printf '\nSaved module checksum:\n'
sha256sum "$destination/it87.ko"
printf '\nLoader prepared: %s/load-it87.sh\n' "$loader_dir"
printf 'Add this script as an enabled Post Init task in the TrueNAS portal.\n'
