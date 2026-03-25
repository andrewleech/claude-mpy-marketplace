#!/usr/bin/env bash
# ci-local.sh — run the MicroPython CI pipeline locally using Docker.
#
# Usage:
#   ./ci/ci-local.sh [--build] TARGET [TARGET...]
#   ./ci/ci-local.sh --build         # build image only
#   ./ci/ci-local.sh all             # run every target
#
# Targets (ports):
#   stm32  unix  unix-qemu  esp32  esp8266  rp2  qemu  cc3200  mimxrt
#   nrf  powerpc  renesas  samd  alif  webassembly  windows  zephyr
#
# Targets (checks):
#   commit-format  format  codespell  ruff  biome  docs  examples  mpy-format
#   mpremote
#
# Meta targets:
#   all  all-checks
#
# The image (~15–20 GB) is built from the repo root:
#   docker build -f ci/Dockerfile -t micropython-ci .
#
# Notes:
#   - esp32 and webassembly targets create symlinks in the repo root
#     (esp-idf -> /opt/esp-idf, emsdk -> /opt/emsdk) so that the relative
#     'source esp-idf/export.sh' and 'source emsdk/emsdk_env.sh' calls in
#     ci.sh resolve correctly inside the container.  Both are gitignored.
#   - unix-qemu requires binfmt_misc handlers for MIPS, ARM and RISC-V on
#     the host.  Register them once with:
#       docker run --rm --privileged multiarch/qemu-user-static --reset
#     Do NOT use -p yes (fix-binary) — the container's qemu-user-static must
#     be used so that the /usr/gnemul/ sysroot symlinks resolve correctly.
#     After registration, disable the mipsn32 handlers whose magic patterns
#     overlap with mips and cause the wrong emulator to be selected:
#       echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32 >/dev/null
#       echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-mipsn32el >/dev/null
#   - zephyr runs directly on the host (ci.sh manages its own Docker
#     container).  Requires docker access and ~15 GB for the west workspace.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_IMAGE="${MICROPYTHON_CI_IMAGE:-micropython-ci:latest}"

# ── helpers ───────────────────────────────────────────────────────────────────

usage() {
    sed -n '/^# Usage/,/^[^#]/{ /^#/{ s/^# \{0,1\}//; p } }' "${BASH_SOURCE[0]}"
    exit 0
}

die() { echo "ci-local: error: $*" >&2; exit 1; }

build_image() {
    echo "==> Building $CI_IMAGE from $REPO_ROOT"
    docker build -f "$REPO_ROOT/ci/Dockerfile" -t "$CI_IMAGE" "$REPO_ROOT"
}

# Run one or more ci.sh functions inside the main container.
# Usage: run_in_container "func1 && func2 && ..."
run_in_container() {
    docker run --rm \
        -v "$REPO_ROOT:$REPO_ROOT" \
        -w "$REPO_ROOT" \
        --user "$(id -u):$(id -g)" \
        -v "$HOME:$HOME" -e HOME="$HOME" \
        -e MAKEOPTS="${MAKEOPTS:-}" \
        "$CI_IMAGE" \
        bash -c "git config --global --add safe.directory '*' 2>/dev/null; source tools/ci.sh && $1"
}

# Create a symlink in the repo root that will be valid inside the container.
# The symlink is dangling on the host but resolves inside the container where
# /opt/<name> exists.
ensure_symlink() {
    local name="$1" target="$2"
    if [[ ! -L "$REPO_ROOT/$name" ]]; then
        ln -sfn "$target" "$REPO_ROOT/$name"
    fi
}

# ── targets ───────────────────────────────────────────────────────────────────

run_stm32() {
    echo "==> stm32"
    # ARM GNU Toolchain 14.3 is already in PATH via the Dockerfile ENV.
    # ci_stm32_path prepends a non-existent relative path; the toolchain is
    # already accessible via the pre-set PATH so that has no ill effect.
    run_in_container "
        ci_stm32_pyb_build &&
        ci_stm32_nucleo_build &&
        ci_stm32_misc_build
    "
}

run_unix() {
    echo "==> unix"
    run_in_container "
        ci_unix_minimal_build &&
        ci_unix_minimal_run_tests &&
        ci_unix_standard_build &&
        ci_unix_standard_run_tests &&
        ci_unix_standard_v2_build &&
        ci_unix_standard_v2_run_tests &&
        ci_unix_coverage_build &&
        ci_unix_coverage_run_tests &&
        ci_unix_coverage_run_mpy_merge_tests &&
        ci_unix_coverage_run_native_mpy_tests &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_coverage_32bit_build &&
        ci_unix_coverage_32bit_run_tests &&
        ci_unix_coverage_32bit_run_native_mpy_tests &&
        ci_unix_nanbox_build &&
        ci_unix_nanbox_run_tests &&
        ci_unix_build_ffi_lib_helper gcc -m32 &&
        ci_unix_longlong_build &&
        ci_unix_longlong_run_tests &&
        ci_unix_build_ffi_lib_helper gcc &&
        ci_unix_float_build &&
        ci_unix_float_run_tests &&
        ci_unix_gil_enabled_build &&
        ci_unix_gil_enabled_run_tests &&
        ci_unix_stackless_clang_build &&
        ci_unix_stackless_clang_run_tests &&
        ci_unix_float_clang_build &&
        ci_unix_float_clang_run_tests &&
        ci_unix_settrace_stackless_build &&
        ci_unix_settrace_stackless_run_tests &&
        ci_unix_repr_b_build &&
        ci_unix_build_ffi_lib_helper gcc &&
        ci_unix_repr_b_run_tests &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_sanitize_undefined_build &&
        ci_unix_sanitize_undefined_run_tests &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_sanitize_address_build &&
        ci_unix_sanitize_address_run_tests
    "
}

run_unix_qemu() {
    echo "==> unix-qemu"
    run_in_container "
        rm -f tests/ports/unix/ffi_lib.so &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_qemu_mips_build &&
        (ci_unix_qemu_mips_run_tests || true) &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_qemu_arm_build &&
        (ci_unix_qemu_arm_run_tests || true) &&
        make ${MAKEOPTS:-} -C ports/unix VARIANT=coverage clean &&
        ci_unix_qemu_riscv64_build &&
        (ci_unix_qemu_riscv64_run_tests || true)
    "
}

run_esp32() {
    echo "==> esp32"
    ensure_symlink esp-idf /opt/esp-idf
    run_in_container "
        ci_esp32_build_cmod_spiram_s2 &&
        ci_esp32_build_s3_c3 &&
        ci_esp32_build_c2_c5_c6 &&
        ci_esp32_build_p4
    "
}

run_esp8266() {
    echo "==> esp8266"
    # /opt/xtensa-lx106-elf/bin is already in PATH via the Dockerfile ENV.
    run_in_container "ci_esp8266_build"
}

run_rp2() {
    echo "==> rp2"
    run_in_container "ci_rp2_build"
}

run_qemu() {
    echo "==> qemu"
    run_in_container "
        ci_qemu_build_arm_bigendian &&
        (ci_qemu_build_arm_sabrelite || true) &&
        (ci_qemu_build_arm_thumb_softfp || true) &&
        (ci_qemu_build_arm_thumb_hardfp || true) &&
        (ci_qemu_build_rv32 || true) &&
        (ci_qemu_build_rv64 || true)
    "
}

run_cc3200() {
    echo "==> cc3200"
    run_in_container "ci_cc3200_build"
}

run_mimxrt() {
    echo "==> mimxrt"
    run_in_container "ci_mimxrt_build"
}

run_nrf() {
    echo "==> nrf"
    run_in_container "ci_nrf_build"
}

run_powerpc() {
    echo "==> powerpc"
    run_in_container "ci_powerpc_build"
}

run_renesas() {
    echo "==> renesas"
    run_in_container "ci_renesas_ra_board_build"
}

run_samd() {
    echo "==> samd"
    run_in_container "ci_samd_build"
}

run_alif() {
    echo "==> alif"
    run_in_container "ci_alif_ae3_build"
}

run_webassembly() {
    echo "==> webassembly"
    ensure_symlink emsdk /opt/emsdk
    run_in_container "
        ci_webassembly_build &&
        ci_webassembly_run_tests
    "
}

run_windows() {
    echo "==> windows (MinGW cross-compile)"
    run_in_container "ci_windows_build"
}

run_zephyr() {
    echo "==> zephyr (running on host — ci.sh manages its own Docker container)"
    # ci_zephyr_setup tries to 'sudo apt-get install qemu-system-arm'.
    # Skip that if it's already available to avoid unnecessary sudo prompts.
    if command -v qemu-system-arm &>/dev/null; then
        echo "    qemu-system-arm already present, skipping apt-get step"
        (
            cd "$REPO_ROOT"
            # shellcheck source=../tools/ci.sh
            source tools/ci.sh
            # Run setup without the apt-get step by redefining the host part.
            ZEPHYR_DOCKER_VERSION="${ZEPHYR_DOCKER_VERSION:-v0.28.1}"
            IMAGE="ghcr.io/zephyrproject-rtos/ci:${ZEPHYR_DOCKER_VERSION}"
            docker pull "${IMAGE}"
            ZEPHYRPROJECT_DIR="$(pwd)/zephyrproject"
            CCACHE_DIR="$(pwd)/.ccache"
            mkdir -p "${ZEPHYRPROJECT_DIR}" "${CCACHE_DIR}"
            docker rm -f zephyr-ci 2>/dev/null || true
            docker run --name zephyr-ci -d -it \
                -v "$(pwd)":/micropython \
                -v "${ZEPHYRPROJECT_DIR}":/zephyrproject \
                -v "${CCACHE_DIR}":/root/.cache/ccache \
                -e ZEPHYR_SDK_INSTALL_DIR="/opt/toolchains/zephyr-sdk-${ZEPHYR_SDK_VERSION:-0.17.2}" \
                -e ZEPHYR_TOOLCHAIN_VARIANT=zephyr \
                -e ZEPHYR_BASE=/zephyrproject/zephyr \
                -w /micropython/ports/zephyr \
                "${IMAGE}"
            ci_zephyr_install
            ci_zephyr_build
            ci_zephyr_run_tests
        )
    else
        (
            cd "$REPO_ROOT"
            # shellcheck source=../tools/ci.sh
            source tools/ci.sh
            docker rm -f zephyr-ci 2>/dev/null || true
            ci_zephyr_setup
            ci_zephyr_install
            ci_zephyr_build
            ci_zephyr_run_tests
        )
    fi
}

run_format() {
    echo "==> format"
    run_in_container "ci_c_code_formatting_run"
}

run_commit_format() {
    echo "==> commit-format"
    run_in_container "
        MERGE_BASE=\$(git merge-base upstream/master HEAD) &&
        tools/verifygitlog.py -v \${MERGE_BASE}..HEAD
    "
}

run_codespell() {
    echo "==> codespell"
    run_in_container "
        codespell &&
        if git grep -n Micropython -- ':(exclude).github/workflows/codespell.yml'; then
            echo 'Please correct capitalisation of MicroPython on the above lines'
            exit 1
        fi
    "
}

run_ruff() {
    echo "==> ruff"
    run_in_container "
        ruff check . &&
        ruff format --diff .
    "
}

run_biome() {
    echo "==> biome"
    run_in_container "git ls-files 'tests/*.js' 'tests/*.mjs' 'ports/webassembly/*.js' 'ports/webassembly/*.mjs' | xargs biome ci --indent-style=space --indent-width=4"
}

run_docs() {
    echo "==> docs"
    run_in_container "
        ci_unix_build_helper &&
        make -C docs/ html
    "
}

run_examples() {
    echo "==> examples"
    run_in_container "ci_embedding_build"
}

run_mpy_format() {
    echo "==> mpy-format"
    run_in_container "
        ci_mpy_format_test &&
        ci_mpy_cross_debug_emitter
    "
}

run_mpremote() {
    echo "==> mpremote"
    run_in_container "cd tools/mpremote && python3 -m build --wheel"
}

run_all_checks() {
    run_commit_format
    run_format
    run_codespell
    run_ruff
    run_biome
    run_docs
    run_examples
    run_mpy_format
    run_mpremote
}

run_all() {
    run_all_checks
    run_format
    run_unix
    run_unix_qemu
    run_stm32
    run_esp32
    run_esp8266
    run_rp2
    run_qemu
    run_cc3200
    run_mimxrt
    run_nrf
    run_powerpc
    run_renesas
    run_samd
    run_alif
    run_webassembly
    run_windows
    run_zephyr
}

# ── argument parsing ───────────────────────────────────────────────────────────

[[ $# -eq 0 ]] && usage

BUILD=0
TARGETS=()

for arg in "$@"; do
    case "$arg" in
        --build)  BUILD=1 ;;
        -h|--help) usage ;;
        *)        TARGETS+=("$arg") ;;
    esac
done

[[ $BUILD -eq 1 ]] && build_image
[[ ${#TARGETS[@]} -eq 0 ]] && exit 0

for target in "${TARGETS[@]}"; do
    case "$target" in
        stm32)        run_stm32 ;;
        unix)         run_unix ;;
        unix-qemu)    run_unix_qemu ;;
        esp32)        run_esp32 ;;
        esp8266)      run_esp8266 ;;
        rp2)          run_rp2 ;;
        qemu)         run_qemu ;;
        cc3200)       run_cc3200 ;;
        mimxrt)       run_mimxrt ;;
        nrf)          run_nrf ;;
        powerpc)      run_powerpc ;;
        renesas)      run_renesas ;;
        samd)         run_samd ;;
        alif)         run_alif ;;
        webassembly)  run_webassembly ;;
        windows)      run_windows ;;
        zephyr)       run_zephyr ;;
        format)       run_format ;;
        commit-format) run_commit_format ;;
        codespell)    run_codespell ;;
        ruff)         run_ruff ;;
        biome)        run_biome ;;
        docs)         run_docs ;;
        examples)     run_examples ;;
        mpy-format)   run_mpy_format ;;
        mpremote)     run_mpremote ;;
        all-checks)   run_all_checks ;;
        all)          run_all ;;
        *)            die "unknown target '$target'. Run with --help for usage." ;;
    esac
done
