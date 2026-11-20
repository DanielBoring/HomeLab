#!/bin/bash
# Build only: never install/load a module or replace the firmware baseline.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    printf 'Run on TrueNAS as root using sudo bash.\n' >&2
    exit 1
fi
mountpoint -q /mnt/SSD || { printf 'SSD pool is not mounted.\n' >&2; exit 1; }

kernel_release="$(uname -r)"
headers_dir="$(readlink -f "/lib/modules/$kernel_release/build")"
test -f "$headers_dir/Makefile"
test -f "$headers_dir/Module.symvers"
test "$(cat "$headers_dir/include/config/kernel.release")" = "$kernel_release"
if ! grep -Eq 'gcc .*12\.2\.0' /proc/version; then
    printf 'This recipe selects GCC 12.2; review /proc/version before adapting it.\n' >&2
    exit 1
fi

build_root=/mnt/SSD/Containers/it8613e-fan-control/builds
install -d -m 0750 "$build_root"
build_dir="$(mktemp -d "$build_root/$kernel_release.XXXXXX")"
exec > >(tee "$build_dir/build.log") 2>&1
printf 'Build directory: %s\n' "$build_dir"
cat /proc/version | tee "$build_dir/kernel-version.txt"
sha256sum "$headers_dir/Module.symvers" > "$build_dir/headers-symvers.sha256"

docker run --rm --platform linux/amd64 \
    --mount type=bind,src=/usr/src,dst=/usr/src,readonly \
    --mount "type=bind,src=$build_dir,dst=/work" \
    --env "KERNEL_HEADERS=$headers_dir" \
    --env "EXPECTED_KERNEL=$kernel_release" \
    debian:bookworm-slim bash -euo pipefail -c '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y --no-install-recommends \
            gcc-12 make git ca-certificates libelf-dev bc kmod
        git init /work/driver
        git -C /work/driver remote add origin https://github.com/frankcrawford/it87.git
        git -C /work/driver fetch --depth=1 origin \
            bc06d3488439e5fcd725c1bdcfcac994d6d95cac
        git -C /work/driver checkout --detach FETCH_HEAD
        test "$(git -C /work/driver rev-parse HEAD)" = \
            bc06d3488439e5fcd725c1bdcfcac994d6d95cac
        git -C /work/driver rev-parse HEAD > /work/source-commit.txt
        gcc-12 --version > /work/compiler-version.txt
        dpkg-query -W > /work/builder-packages.txt
        make -C "$KERNEL_HEADERS" M=/work/driver CC=gcc-12 modules
        module_vermagic="$(modinfo -F vermagic /work/driver/it87.ko)"
        [[ "$module_vermagic" == "$EXPECTED_KERNEL "* ]]
        modinfo /work/driver/it87.ko > /work/module-info.txt
    '

docker image inspect debian:bookworm-slim \
    --format '{{.Id}} {{json .RepoDigests}}' > "$build_dir/builder-image.txt"
printf '\n=== Built module ===\n'
cat "$build_dir/module-info.txt"
sha256sum "$build_dir/driver/it87.ko" | tee "$build_dir/module.sha256"
printf '\nBuild complete: %s/driver/it87.ko\n' "$build_dir"
printf 'No module was installed or loaded; baseline and containers are unchanged.\n'
