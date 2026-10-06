# ASUS Vivobook 14 Flip (TP3407SA) Speaker Fix

This folder contains the hardware activation fix and installation scripts for the Texas Instruments TAS2781 smart amplifier on the ASUS Vivobook 14 Flip (TP3407SA).

## Files

- **`asus-sound-fix.c`**: C source code that communicates with the TAS2781 smart amplifier chips over the I2C bus (`/dev/i2c-0`) to initialize registers, unmute amplifiers, and set operational volume.
- **`asus-sound-fix`**: Precompiled 64-bit binary created from `asus-sound-fix.c`.
- **`install-speaker-fix.sh`**: Setup script that installs `asus-sound-fix` to `/usr/local/bin`, activates amplifiers, and registers systemd services (`asus-sound-fix.service` and `asus-sound-fix-resume.service`) to keep audio working across boots and sleep/wake cycles.
- **`fix-speaker-driver.sh`**: Helper script to ensure required TAS2781 kernel firmware symlinks exist in `/lib/firmware`.
