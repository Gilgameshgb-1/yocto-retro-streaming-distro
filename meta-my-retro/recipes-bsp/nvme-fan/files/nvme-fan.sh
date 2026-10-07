#!/bin/sh
# nvme-fan.sh — Speed the Pi 5 fan up when the NVMe SSD gets hot.
#
# The kernel drives the fan from the CPU temperature only (the cpu-thermal
# zone, with the curve set by the fan_temp* dtparams in config.txt). The SSD
# sits on a HAT and heats up on long downloads while the CPU idles, so this
# watches the SSD as well:
#
#   SSD >= ON_TEMP   take the fan over, at the faster of the SSD level and
#                    the level the CPU curve would ask for
#   SSD <  OFF_TEMP  hand the fan back to the kernel
#
# Taking over means switching the cpu-thermal zone to "disabled"; otherwise
# the kernel resets the fan speed within a second. It is switched back on
# whenever the SSD cools down, the SSD stops reporting, or this service
# stops. The Pi firmware throttles the CPU on its own if it ever overheats,
# independently of this.
#
# Usage: nvme-fan.sh            run the loop
#        nvme-fan.sh --release  give the fan back to the kernel and exit

ON_TEMP=${NVME_FAN_ON:-50000}       # m°C: SSD temperature that starts the override
OFF_TEMP=${NVME_FAN_OFF:-45000}     # m°C: hand back below this (hysteresis)
INTERVAL=${NVME_FAN_INTERVAL:-5}    # seconds between checks

# SSD temperature -> fan PWM (0-255).
nvme_level() {
    if   [ "$1" -ge 65000 ]; then echo 255
    elif [ "$1" -ge 60000 ]; then echo 200
    elif [ "$1" -ge 55000 ]; then echo 160
    else                          echo 120
    fi
}

# Mirror of the kernel's CPU curve (fan_temp0..3 in config.txt), so taking
# the fan over never runs it slower than the kernel would have. Keep in step
# with RPI_EXTRA_CONFIG in kas-project.yml.
cpu_level() {
    if   [ "$1" -ge 75000 ]; then echo 250
    elif [ "$1" -ge 67500 ]; then echo 175
    elif [ "$1" -ge 60000 ]; then echo 125
    elif [ "$1" -ge 35000 ]; then echo 90
    else                          echo 0
    fi
}

find_hwmon() {
    for h in /sys/class/hwmon/hwmon*; do
        [ "$(cat "$h/name" 2>/dev/null)" = "$1" ] && { echo "$h"; return 0; }
    done
    return 1
}

find_zone() {
    for z in /sys/class/thermal/thermal_zone*; do
        [ "$(cat "$z/type" 2>/dev/null)" = cpu-thermal ] && { echo "$z"; return 0; }
    done
    return 1
}

ZONE=$(find_zone) || { echo "no cpu-thermal zone found"; exit 1; }
FAN=$(find_hwmon pwmfan)

# Hand the fan back. Set the CPU-curve speed first: the kernel only rewrites
# the fan when the CPU crosses one of its thresholds, so without this a fan
# left at full speed would stay there.
release() {
    [ -n "$FAN" ] && cpu_level "$(cat "$ZONE/temp")" > "$FAN/pwm1"
    echo enabled > "$ZONE/mode"
}

if [ "$1" = "--release" ]; then
    release
    exit 0
fi

[ -n "$FAN" ] || { echo "no pwmfan found - is a fan on the FAN header?"; exit 1; }

overriding=0
trap 'release; exit 0' TERM INT

echo "watching the SSD: fan override from $((ON_TEMP / 1000))C, back to the kernel below $((OFF_TEMP / 1000))C"

while true; do
    # Looked up every time: the nvme hwmon only exists while the drive is up.
    NVME=$(find_hwmon nvme)
    nvme_t=$(cat "$NVME/temp1_input" 2>/dev/null) || nvme_t=""

    hot=0
    if [ -n "$nvme_t" ]; then
        if [ "$nvme_t" -ge "$ON_TEMP" ]; then
            hot=1
        elif [ "$overriding" = 1 ] && [ "$nvme_t" -ge "$OFF_TEMP" ]; then
            hot=1
        fi
    fi

    if [ "$hot" = 1 ]; then
        want=$(nvme_level "$nvme_t")
        cpu=$(cpu_level "$(cat "$ZONE/temp")")
        [ "$cpu" -gt "$want" ] && want=$cpu
        if [ "$overriding" = 0 ]; then
            echo "SSD at $((nvme_t / 1000))C - taking the fan over"
            echo disabled > "$ZONE/mode"
            overriding=1
        fi
        echo "$want" > "$FAN/pwm1"
    elif [ "$overriding" = 1 ]; then
        if [ -n "$nvme_t" ]; then now="$((nvme_t / 1000))C"; else now="not reporting"; fi
        echo "SSD $now - fan back to the kernel"
        release
        overriding=0
    fi

    sleep "$INTERVAL" &
    wait $!
done
