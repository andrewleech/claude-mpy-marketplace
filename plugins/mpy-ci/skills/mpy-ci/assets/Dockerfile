FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# ── Layer 1: base build tools ────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        cmake \
        curl \
        git \
        libffi-dev \
        libtool \
        ninja-build \
        nodejs \
        npm \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        unzip \
        wget \
        zip \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 2: uncrustify 0.72 (matches ubuntu-22.04 used by upstream CI) ─────
# Ubuntu 24.04 ships 0.78 which produces different formatting output.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpcre3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q -O /tmp/uncrustify.tar.gz \
        'https://github.com/uncrustify/uncrustify/archive/refs/tags/uncrustify-0.72.0.tar.gz' \
    && tar xzf /tmp/uncrustify.tar.gz -C /tmp \
    && cmake -S /tmp/uncrustify-uncrustify-0.72.0 -B /tmp/uncrustify-build \
    && make -j"$(nproc)" -C /tmp/uncrustify-build \
    && make -C /tmp/uncrustify-build install \
    && rm -rf /tmp/uncrustify*

# ── Layer 3: i386 architecture + multilib (32-bit unix tests) ────────────────
RUN dpkg --add-architecture i386 \
    && apt-get update && apt-get install -y --no-install-recommends \
        gcc-multilib \
        g++-multilib \
        libffi-dev:i386 \
        linux-libc-dev:i386 \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 4: cross-compilers and QEMU ────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc-arm-none-eabi \
        libnewlib-arm-none-eabi \
        gcc-riscv64-unknown-elf \
        picolibc-riscv64-unknown-elf \
        gcc-powerpc64le-linux-gnu \
        libc6-dev-ppc64el-cross \
        gcc-mips-linux-gnu \
        g++-mips-linux-gnu \
        libc6-mips-cross \
        libltdl-dev \
        gcc-arm-linux-gnueabi \
        g++-arm-linux-gnueabi \
        gcc-riscv64-linux-gnu \
        g++-riscv64-linux-gnu \
        gcc-mingw-w64 \
        protobuf-c-compiler \
        qemu-system \
        qemu-user-static \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/gnemul \
    && ln -s /usr/mips-linux-gnu    /usr/gnemul/qemu-mips \
    && ln -s /usr/arm-linux-gnueabi /usr/gnemul/qemu-arm \
    && ln -s /usr/riscv64-linux-gnu /usr/gnemul/qemu-riscv64

# ── Layer 5: Python packages ─────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --break-system-packages \
        setuptools \
        pyelftools \
        ar \
        pyhy \
        pyserial \
        'esptool==3.3.1' \
        'codespell==2.4.1' \
        tomli \
        'ruff==0.11.6' \
        build \
        'sphinx~=7.2.6' \
        'sphinxcontrib.jquery==4.1' \
        'sphinx-rtd-theme==3.0.2' \
    && npm install -g @biomejs/biome@1.5.3

# ── Layer 6: ARM GNU Toolchain 14.3.rel1 (STM32, needed for Cortex-M55) ─────
RUN wget -q -O /tmp/arm-toolchain.tar.xz \
        'https://developer.arm.com/-/media/Files/downloads/gnu/14.3.rel1/binrel/arm-gnu-toolchain-14.3.rel1-x86_64-arm-none-eabi.tar.xz' \
    && xzcat /tmp/arm-toolchain.tar.xz | tar x -C /opt/ \
    && rm /tmp/arm-toolchain.tar.xz

# ── Layer 7: ESP8266 xtensa toolchain ────────────────────────────────────────
RUN wget -q -O /tmp/xtensa.tar.gz \
        'https://micropython.org/resources/xtensa-lx106-elf-standalone.tar.gz' \
    && zcat /tmp/xtensa.tar.gz | tar x -C /opt/ \
    && rm /opt/xtensa-lx106-elf/bin/esptool.py \
    && rm /tmp/xtensa.tar.gz

# ── Layer 8: pico-sdk + picotool (RP2) ───────────────────────────────────────
RUN git clone --depth 1 https://github.com/raspberrypi/pico-sdk.git /opt/pico-sdk \
    && cd /opt/pico-sdk && git submodule update --init lib/mbedtls \
    && git clone --depth 1 https://github.com/raspberrypi/picotool.git /tmp/picotool \
    && cmake -S /tmp/picotool -B /tmp/picotool/build \
             -DPICO_SDK_PATH=/opt/pico-sdk \
    && make -j"$(nproc)" -C /tmp/picotool/build \
    && make -C /tmp/picotool/build install \
    && rm -rf /tmp/picotool

# ── Layer 9: ESP-IDF (version derived from the repo lockfile) ─────────────────
# The lockfile is copied so Docker can cache this layer independently of other
# source changes.  The grep/sed matches what ci.sh line 212 does at runtime.
COPY ports/esp32/lockfiles/dependencies.lock.esp32 /tmp/esp32-lockfile

ENV IDF_PATH=/opt/esp-idf
ENV IDF_TOOLS_PATH=/opt/esp-idf-tools
ENV IDF_CCACHE_ENABLE=1

RUN IDF_VER=v$(grep -A10 "idf:" /tmp/esp32-lockfile \
                | grep "version:" | head -n1 \
                | sed -E 's/ +version: //') \
    && echo "Installing ESP-IDF $IDF_VER" \
    && git clone --depth 1 --branch "$IDF_VER" \
           https://github.com/espressif/esp-idf.git /opt/esp-idf \
    && cd /opt/esp-idf \
    && git submodule update --init --recursive \
    && ./install.sh esp32,esp32s2,esp32s3,esp32c3,esp32c2,esp32c5,esp32c6,esp32p4 \
    && bash -c "source /opt/esp-idf/export.sh && pip install --no-cache-dir ar" \
    && chmod -R a+rX /opt/esp-idf-tools \
    && rm /tmp/esp32-lockfile

# ── Layer 10: Emscripten SDK ─────────────────────────────────────────────────
ENV EMSDK=/opt/emsdk

RUN git clone https://github.com/emscripten-core/emsdk.git /opt/emsdk \
    && cd /opt/emsdk \
    && ./emsdk install latest \
    && ./emsdk activate latest \
    && chmod -R a+rX /opt/emsdk

# ── Environment ──────────────────────────────────────────────────────────────
ENV PICO_SDK_PATH=/opt/pico-sdk

ENV PATH="/opt/arm-gnu-toolchain-14.3.rel1-x86_64-arm-none-eabi/bin:/opt/xtensa-lx106-elf/bin:${PATH}"
