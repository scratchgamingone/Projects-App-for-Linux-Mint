#!/usr/bin/env bash

echo "=== Adjusting Audio Mixer & Testing Speakers ==="

# Set PipeWire / PulseAudio volume to 150% boost and unmute
pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null || true
pactl set-sink-volume @DEFAULT_SINK@ 150% 2>/dev/null || true

# Set ALSA hardware levels
amixer -c 0 sset 'Master' 100% unmute 2>/dev/null || true
amixer -c 0 sset 'Speaker' unmute 2>/dev/null || true
amixer -c 0 sset 'Line Out' 100% 2>/dev/null || true

# Maximize TAS2781 speaker profile and analog volume
amixer -c 0 cset iface=CARD,name='Speaker Profile Id' 1 2>/dev/null || true
amixer -c 0 cset iface=CARD,name='Speaker Analog Volume' 20 2>/dev/null || true
amixer -c 0 cset iface=CARD,name='Speaker Config Id' 1 2>/dev/null || true
amixer -c 0 cset iface=CARD,name='Speaker Force Firmware Load' on 2>/dev/null || true

# Show current dmesg firmware status
echo ""
echo "=== Kernel TAS2781 Amplifier Status ==="
dmesg | grep -iE 'tas2781|dsp.*10a4' | tail -n 6 || true

echo ""
echo "=== Playing Test Sound ==="
if [ -f "/usr/share/sounds/freedesktop/stereo/bell.oga" ]; then
    paplay /usr/share/sounds/freedesktop/stereo/bell.oga
elif [ -f "/usr/share/sounds/freedesktop/stereo/audio-channel-front-center.oga" ]; then
    paplay /usr/share/sounds/freedesktop/stereo/audio-channel-front-center.oga
else
    speaker-test -t sine -f 440 -l 1 -c 2
fi

echo "Done."
