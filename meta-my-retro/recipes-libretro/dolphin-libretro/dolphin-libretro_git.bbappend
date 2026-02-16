# We don't use this for now since gamecube is giving me a lot of trouble

inherit pkgconfig

DEPENDS:append = " alsa-lib libevdev libxi libxrandr"
DEPENDS:remove = "fmt"

# 1. Use :append to ensure these are added to the final list of flags
EXTRA_OECMAKE:append = " \
    -DUSE_SYSTEM_FMT=OFF \
    -DUSE_SYSTEM_PUGIXML=OFF \
    -DENABLE_X11=OFF \
    -DENABLE_VULKAN=ON \
    -DENABLE_ALSA=ON \
    -DENABLE_PULSEAUDIO=OFF \
    -DENABLE_EGL=ON \
    -DENABLE_GENERIC=ON \
    -DCORE_ARM64=ON \
    -DUSE_SYSTEM_FMT=ON \
    -DUSE_SYSTEM_PUGIXML=ON \
    -DLIBRETRO=ON \
    -DCMAKE_BUILD_TYPE=Release \
"

# Cmake haccks
do_configure:prepend() {
    find ${S} -name "CMakeLists.txt" -exec sed -i 's/-march=armv8-a+crc//g' {} +
    find ${S} -name "CMakeLists.txt" -exec sed -i 's/-march=armv8-a//g' {} +
    find ${S} -name "*.cmake" -exec sed -i 's/-march=armv8-a+crc//g' {} +
    sed -i 's/check_include_file("alsa\/asoundlib.h" ALSA_FOUND)/set(ALSA_FOUND TRUE)/g' ${S}/CMakeLists.txt || true
}