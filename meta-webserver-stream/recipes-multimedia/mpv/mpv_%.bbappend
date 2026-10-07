# Video on the console (no X or Wayland session): DRM/KMS with EGL on GBM.
# That gives mpv --vo=gpu --gpu-context=drm, which scales on the GPU and can
# take hardware-decoded HEVC frames straight from the decoder (--hwdec=drm).
# --vo=drm alone scales every frame on the CPU, which cannot keep up with 4K.
#
# egl-drm needs gbm: enabling egl without gbm is what used to fail configure.
# Wayland stays off; gl-wayland is not needed on a console-only box.
PACKAGECONFIG:append = " drm gbm egl"
PACKAGECONFIG:remove = "wayland"
EXTRA_OECONF:append = " --enable-libmpv-shared"
