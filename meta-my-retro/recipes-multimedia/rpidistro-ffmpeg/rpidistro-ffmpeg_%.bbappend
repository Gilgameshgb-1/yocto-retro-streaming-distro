# Hardware HEVC decoding on the Pi 5 (rpivid, /dev/video19).
#
# The Raspberry Pi patch set ships a V4L2 request API hwaccel for rpivid,
# but configure leaves it off ("--enable-v4l2-request [no]"), and the recipe
# drops the SAND frame formats that rpivid outputs whenever vc4graphics is
# set, which is always on a Pi 5. Without both, 4K HEVC Main 10 decodes on
# the CPU at ~9 fps against the 24 fps a film needs.
PACKAGECONFIG:append = " sand"
EXTRA_OECONF:append = " --enable-v4l2-request"

# The hwaccel carries private copies of three pre-upstream revisions of the
# kernel's HEVC stateless API (v1-v3) next to the upstream one (v4). Kernel
# headers from 6.0 on define the same structs, so v1-v3 no longer compile.
# The Pi 5 kernel only speaks v4: build just that, and point the fallback
# probes at it too.
rpi5_hevc_v4_only() {
    sed -i 's/v4l2_req_hevc_v1\.o v4l2_req_hevc_v2\.o v4l2_req_hevc_v3\.o *v4l2_req_hevc_v4\.o/v4l2_req_hevc_v4.o/' \
        ${S}/libavcodec/Makefile
    sed -i 's/V2(ff_v4l2_req_hevc, [123])/V2(ff_v4l2_req_hevc, 4)/g' \
        ${S}/libavcodec/v4l2_request_hevc.c
    grep -q 'v4l2_req_hevc_v1\.o' ${S}/libavcodec/Makefile && bbfatal "rpi5_hevc_v4_only: Makefile edit did not apply"
    true
}
do_patch[postfuncs] += "rpi5_hevc_v4_only"

# Copying a 10-bit decoded frame back to RAM (mpv --hwdec=drm-copy) unpacks
# its chroma with a NEON routine that reads ~138 KB past the end of a 4K frame
# on the last row and segfaults. Use the plain C version for chroma; luma keeps
# its NEON path, which stays inside the frame.
rpi_sand30_c16_use_c() {
    sed -i '/^void av_rpi_sand30_to_planar_c16/,/ff_rpi_sand30_lines_to_planar_c16(dst_u/ s|if (_x == 0) {|if (0) { /* NEON c16 over-reads the last row */|' \
        ${S}/libavutil/rpi_sand_fns.c
    grep -q 'NEON c16 over-reads' ${S}/libavutil/rpi_sand_fns.c || bbfatal "rpi_sand30_c16_use_c: edit did not apply"
}
do_patch[postfuncs] += "rpi_sand30_c16_use_c"
