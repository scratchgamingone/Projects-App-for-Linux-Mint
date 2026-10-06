#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>

#ifndef I2C_SLAVE_FORCE
#define I2C_SLAVE_FORCE 0x0706
#endif

struct reg_val {
    unsigned char reg;
    unsigned char val;
};

static const struct reg_val reg_seq[] = {
    {0x00, 0x00},
    {0x7f, 0x00},
    {0x01, 0x01},
    {0x0e, 0xc4},
    {0x0f, 0x40},
    {0x5c, 0xd9},
    {0x60, 0x10},
    {0x0a, 0x00}, // Channel select: 0x1e for left (0x38), 0x2e for right (0x3d)
    {0x0d, 0x01},
    {0x16, 0x40}, // Speaker protection / gain configuration
    {0x00, 0x01},
    {0x17, 0xc8},
    {0x00, 0x04},
    {0x30, 0x00},
    {0x31, 0x00},
    {0x32, 0x00},
    {0x33, 0x01},
    {0x00, 0x08},
    {0x18, 0x00},
    {0x19, 0x00},
    {0x1a, 0x00},
    {0x1b, 0x00},
    {0x28, 0x40},
    {0x29, 0x00},
    {0x2a, 0x00},
    {0x2b, 0x00},
    {0x00, 0x0a},
    {0x48, 0x00},
    {0x49, 0x00},
    {0x4a, 0x00},
    {0x4b, 0x00},
    {0x58, 0x40},
    {0x59, 0x00},
    {0x5a, 0x00},
    {0x5b, 0x00},
    {0x00, 0x00},
    {0x02, 0x00}, // Power state: active / unmute
};

static const unsigned short chip_addrs[] = {0x38, 0x3d};

int find_tias2781_bus(void) {
    const char *sysfs_path = "/sys/bus/i2c/devices";
    DIR *d = opendir(sysfs_path);
    if (!d) return 0;

    struct dirent *dir;
    char target[512];
    int bus = -1;

    while ((dir = readdir(d)) != NULL) {
        if (strstr(dir->d_name, "TIAS2781")) {
            char path[512];
            snprintf(path, sizeof(path), "%s/%s", sysfs_path, dir->d_name);
            ssize_t len = readlink(path, target, sizeof(target) - 1);
            if (len != -1) {
                target[len] = '\0';
                char *p = strstr(target, "/i2c-");
                if (p) {
                    bus = atoi(p + 5);
                    break;
                }
            }
        }
    }
    closedir(d);

    if (bus >= 0) {
        return bus;
    }
    return 0; // Fallback to i2c-0
}

int configure_chip(const char *dev_path, unsigned short addr) {
    int fd = open(dev_path, O_RDWR);
    if (fd < 0) {
        fprintf(stderr, "Failed to open %s: %s\n", dev_path, strerror(errno));
        return -1;
    }

    if (ioctl(fd, I2C_SLAVE_FORCE, (unsigned long)addr) < 0) {
        fprintf(stderr, "Failed to force slave address 0x%02x: %s\n", addr, strerror(errno));
        close(fd);
        return -1;
    }

    size_t num_regs = sizeof(reg_seq) / sizeof(reg_seq[0]);
    for (size_t i = 0; i < num_regs; i++) {
        unsigned char reg = reg_seq[i].reg;
        unsigned char val = reg_seq[i].val;

        if (reg == 0x0a) {
            val = (addr == 0x38) ? 0x1e : 0x2e;
        }

        unsigned char buf[2] = {reg, val};
        if (write(fd, buf, 2) != 2) {
            fprintf(stderr, "Failed write to 0x%02x (reg 0x%02x = 0x%02x): %s\n",
                    addr, reg, val, strerror(errno));
            close(fd);
            return -1;
        }
        usleep(1000); // 1ms delay between register writes
    }

    close(fd);
    printf("Successfully activated TAS2781 smart amplifier at 0x%02x (%s channel)\n",
           addr, (addr == 0x38) ? "Left" : "Right");
    return 0;
}

int main(int argc, char *argv[]) {
    int bus = -1;
    if (argc > 1) {
        bus = atoi(argv[1]);
    }
    if (bus < 0) {
        bus = find_tias2781_bus();
    }
    printf("Detected TAS2781 I2C bus: i2c-%d\n", bus);

    char dev_path[64];
    snprintf(dev_path, sizeof(dev_path), "/dev/i2c-%d", bus);

    int errors = 0;
    for (size_t c = 0; c < sizeof(chip_addrs) / sizeof(chip_addrs[0]); c++) {
        unsigned short addr = chip_addrs[c];
        int success = 0;
        for (int attempt = 1; attempt <= 5; attempt++) {
            if (configure_chip(dev_path, addr) == 0) {
                success = 1;
                break;
            }
            usleep(500000); // 500ms retry delay
        }
        if (!success) {
            errors++;
        }
    }

    if (errors > 0) {
        fprintf(stderr, "Error: Failed to configure one or more amplifier chips\n");
        return 1;
    }

    printf("Both internal speaker smart amplifiers are now ON and ready!\n");
    return 0;
}
