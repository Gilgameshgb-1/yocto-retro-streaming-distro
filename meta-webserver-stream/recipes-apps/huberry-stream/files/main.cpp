#include <iostream>
#include <fmt/core.h>
#include <mpv/client.h>

// Only for debugging
void check_mpv_error(int status) {
    if (status < 0) {
        fmt::print("mpv API error: {}\n", mpv_error_string(status));
        exit(1);
    }
}

int main() {
    // engine context
    mpv_handle *ctx = mpv_create();
    if (!ctx) return 1;

    check_mpv_error(mpv_set_option_string(ctx, "force-window", "yes"));
    check_mpv_error(mpv_set_option_string(ctx, "idle", "yes"));

    #ifdef _WIN32
        check_mpv_error(mpv_set_option_string(ctx, "vo", "gpu"));
        check_mpv_error(mpv_set_option_string(ctx, "input-ipc-server", R"(\\.\pipe\mpv-pipe)"));
    #else
        // Render with the GPU straight onto the HDMI output (DRM/KMS), and
        // decode HEVC on the Pi 5's hardware decoder. With "vo=drm" every
        // frame was decoded and scaled on the CPU and 4K stuttered.
        //
        // "drm-copy" copies each decoded frame back to RAM before the GPU
        // scales it: about one core at 4K, no dropped frames. The zero-copy
        // "drm" mode does not work for 10-bit video on this stack: the
        // overlay plane shows nothing and the EGL import shows a blue screen.
        //
        // Codecs without a hardware decoder (H.264 on the Pi 5) fall back to
        // software decoding automatically and still get GPU scaling.
        check_mpv_error(mpv_set_option_string(ctx, "vo", "gpu"));
        check_mpv_error(mpv_set_option_string(ctx, "gpu-context", "drm"));
        check_mpv_error(mpv_set_option_string(ctx, "hwdec", "drm-copy"));
        check_mpv_error(mpv_set_option_string(ctx, "input-ipc-server", "/tmp/mpv-socket"));
    #endif

    check_mpv_error(mpv_initialize(ctx));

    while (true) {
        mpv_event *event = mpv_wait_event(ctx, 0.05);
        if (event->event_id == MPV_EVENT_SHUTDOWN) break;
    }

    mpv_terminate_destroy(ctx);
    return 0;
}
