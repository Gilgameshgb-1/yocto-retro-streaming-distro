SUMMARY = "Linux Userspace x86_64 Emulator recipe"
DESCRIPTION = "Box64 lets you run x86_64 Linux programs on non-x86_64 Linux systems \
like ARM64 in my case: (Raspberry Pi 5)."
HOMEPAGE = "https://github.com/ptitSeb/box64"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRCREV = "${AUTOREV}"
PV = "0.3+git${SRCPV}"

SRC_URI = " \
    git://github.com/ptitSeb/box64;protocol=https;branch=main \
    file://box64.conf \
"

S = "${WORKDIR}/git"

inherit cmake

# Box64 ships pre-built x86_64 libs
# Supress all QA checks and errors while I ponder my orb
INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_SYSROOT_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"
# Insane skips same thing
INSANE_SKIP:${PN} += "already-stripped installed-vs-shipped arch file-rdeps"
SKIP_FILEDEPS:${PN} = "1"

PRIVATE_LIBS = " \
    libgcc_s.so.1 \
    libstdc++.so.5 \
    libstdc++.so.6 \
    libcrypto.so.1.0.0 \
    libcrypto.so.1.1 \
    libssl.so.1.0.0 \
    libssl.so.1.1 \
    libpng12.so.0 \
    libunwind.so.8 \
    libmbedtls.so.12 \
    libmbedtls.so.14 \
    libmbedx509.so.0 \
    libmbedx509.so.1 \
    libmbedcrypto.so.3 \
    libmbedcrypto.so.7 \
"

# Pi 5 specific: enables the ARM64 dynarec tuned for Cortex-A76
# See: https://github.com/ptitSeb/box64/blob/main/docs/COMPILE.md
EXTRA_OECMAKE = " \
    -DRPI5ARM64=1 \
    -DARM_DYNAREC=ON \
    -DHAVE_BOX32=1 \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
"

# More error ignoring
python do_populate_sysroot() {
    bb.build.exec_func("sysroot_stage_all", d)
    import shutil, os
    box64_libs = os.path.join(d.getVar('SYSROOT_DESTDIR'), 'usr/lib/box64-x86_64-linux-gnu')
    if os.path.exists(box64_libs):
        shutil.rmtree(box64_libs)
    bb.build.exec_func("sysroot_strip", d)
}

do_install:append() {
    # so you can just call ./game instead of box64 ./game
    install -d ${D}${sysconfdir}/binfmt.d
    install -m 0644 ${WORKDIR}/box64.conf ${D}${sysconfdir}/binfmt.d/box64.conf
}

FILES:${PN} += " \
    ${sysconfdir}/binfmt.d/box64.conf \
    ${libdir}/box64-x86_64-linux-gnu \
    ${libdir}/box64-x86_64-linux-gnu/* \
"
