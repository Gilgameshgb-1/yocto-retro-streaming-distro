# Enable DRM output (headless HDMI via KMS).
# Remove egl: prevents egl-drm combo failure.
# Remove wayland: wayland enables gl-wayland which also requires egl.
PACKAGECONFIG:append = " drm"
PACKAGECONFIG:remove = "egl wayland"
EXTRA_OECONF:append = " --enable-libmpv-shared --disable-egl-drm"
