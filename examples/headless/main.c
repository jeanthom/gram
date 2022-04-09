#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#include <fcntl.h>
#include <errno.h>
#include <termios.h>
#include <unistd.h>

#include <netinet/in.h>

#include <gram.h>

uint32_t gram_read(struct gramCtx *ctx, void *addr) {
	uint8_t commands[6] = { 0x02, 0x01 };
	uint32_t reply;
	int received, sent, fd;

	fd = *(int*)(ctx->user_data);

	*(uint32_t*)(&commands[2]) = htonl((uint32_t)addr >> 2);

	sent = write(fd, commands, sizeof(commands));
	if (sent != sizeof(commands)) {
		fprintf(stderr, "gram_read error (sent bytes length mismatch)\n");
	}
	received = read(fd, &reply, sizeof(reply));
	if (received != sizeof(reply)) {
		fprintf(stderr, "gram_read error (read bytes length mismatch: %d != %d)\n", received, sizeof(reply));
	}

	//printf("gram_read: 0x%08x: 0x%08x\n", addr, ntohl(reply));

	return ntohl(reply);
}

int gram_write(struct gramCtx *ctx, void *addr, uint32_t value) {
	uint8_t commands[10] = { 0x01, 0x01 };
	int sent;

	*(uint32_t*)(commands+2) = htonl((uint32_t)addr >> 2);
	*(uint32_t*)(commands+6) = htonl(value);

	//printf("gram_write: 0x%08x: 0x%08x\n", addr, value);

	sent = write(*(int*)(ctx->user_data), commands, sizeof(commands));
	if (sent != sizeof(commands)) {
		fprintf(stderr, "gram_write error (sent bytes length mismatch)\n");
		return -1;
	}

	return 0;
}

int serial_setup(const char *devname, int baudrate) {
	struct termios tty;
	int serialfd;
	
	serialfd = open("/dev/ttyUSB1", O_RDWR|O_NOCTTY);
	if (serialfd < 0) {
		fprintf(stderr, "Error %i from open: %s\n", errno, strerror(errno));
	}

	memset(&tty, 0, sizeof(tty));
	if (tcgetattr(serialfd, &tty) != 0) {
		fprintf(stderr, "Error %i from tcgetattr: %s\n", errno, strerror(errno));
	}

	/* Parameters from flterm */
	tcgetattr(serialfd, &tty);
	tty.c_cflag = B115200;
	tty.c_cflag |= CS8;
	tty.c_cflag |= CREAD;
	tty.c_iflag = IGNPAR | IGNBRK;
	tty.c_cflag |= CLOCAL;
	tty.c_oflag = 0;
	tty.c_lflag = 0;
	tty.c_cc[VTIME] = 0;
	tty.c_cc[VMIN] = 1;
	tcsetattr(serialfd, TCSANOW, &tty);
	tcflush(serialfd, TCOFLUSH);
	tcflush(serialfd, TCIFLUSH);

	cfsetispeed(&tty, B115200);
	cfsetospeed(&tty, B115200);

	cfmakeraw(&tty);

	tcflush(serialfd, TCIFLUSH );
	if (tcsetattr(serialfd, TCSANOW, &tty) != 0) {
		fprintf(stderr, "Error %i from tcsetattr: %s\n", errno, strerror(errno));
	}

	return serialfd;
}

int main(int argc, char *argv[]) {
	struct gramCtx ctx;
	int serial_port, baudrate = 0;
	uint32_t read_value, expected_value;
	const size_t kPatternSize = 512;
	uint32_t pattern[kPatternSize];
	const int kDumpWidth = 8;
	size_t i;
	int res;
	uint32_t tmp;
	int delay, miss = 0;

	uint32_t ddr_base = 0x10000000;

#if 0
	struct gramProfile profile = {
		.mode_registers = {
			0xb30, 0x806, 0x200, 0x0
		},
		.rdly_p0 = 2,
		.rdly_p1 = 2,
	};
#endif
#if 0
	struct gramProfile profile = {
		.mode_registers = {
			0xb30, 0x806, 0x200, 0x0
		},
		.rdly_p0 = 2,
		.rdly_p1 = 2,
	};
#endif
#if 1
	struct gramProfile profile = {
		.mode_registers = {
			0xb30, 0x806, 0x200, 0x0
		},
		.rdly_p0 = 5,
		.rdly_p1 = 5,
	};
#endif
#if 0
	struct gramProfile profile = {
		.mode_registers = {
			0x320, 0x6, 0x200, 0x0
		},
		.rdly_p0 = 2,
		.rdly_p1 = 2,
	};
#endif
	struct gramProfile profile2;

	if (argc < 3) {
		fprintf(stderr, "Usage: %s port baudrate\n", argv[0]);
		return EXIT_FAILURE;
	}

	sscanf(argv[2], "%d", &baudrate);
	if (baudrate <= 0) {
		fprintf(stderr, "%d is not a valid baudrate\n", baudrate);
	}

	printf("Port: %s, baudrate: %d\n", argv[1], baudrate);

	serial_port = serial_setup(argv[1], baudrate);
	ctx.user_data = &serial_port;

	printf("gram init... ");
	gram_init(&ctx, &profile, (void*)ddr_base, (void*)0x00009000, (void*)0x00008000);
	printf("done\n");

#if 1
	printf("Rdly\np0: ");
	for (size_t i = 0; i < 8; i++) {
		profile2.rdly_p0 = i;
		gram_load_calibration(&ctx, &profile2);
		gram_reset_burstdet(&ctx);
		for (size_t j = 0; j < 128; j++) {
			tmp = gram_read(&ctx, ddr_base+4*j);
		}
		if (gram_read_burstdet(&ctx, 0)) {
			printf("1");
		} else {
			printf("0");
		}
		fflush(stdout);
	}
	printf("\n");

	printf("Rdly\np1: ");
	for (size_t i = 0; i < 8; i++) {
		profile2.rdly_p1 = i;
		gram_load_calibration(&ctx, &profile2);
		gram_reset_burstdet(&ctx);
		for (size_t j = 0; j < 128; j++) {
			tmp = gram_read(&ctx, ddr_base+4*j);
		}
		if (gram_read_burstdet(&ctx, 1)) {
			printf("1");
		} else {
			printf("0");
		}
		fflush(stdout);
	}
	printf("\n");
#endif

#if 0
        printf("Auto calibrating... ");
        res = gram_generate_calibration(&ctx, &profile2);
        if (res != GRAM_ERR_NONE) {
                printf("failed\n");
                gram_load_calibration(&ctx, &profile);
        } else {
                gram_load_calibration(&ctx, &profile2);
        }
        printf("done\n");

        printf("Auto calibration profile:\n");
        printf("\tp0 rdly: %d\n", profile2.rdly_p0);
        printf("\tp1 rdly: %d\n", profile2.rdly_p1);

	gram_reset_burstdet(&ctx);
#endif

	srand(time(NULL));
	for (i = 0; i < kPatternSize; i++) {
		pattern[i] = rand();
	}

	printf("memtest... \n");

	printf("Writing data sequence...");
	for (i = 0; i < kPatternSize; i++) {
		gram_write(&ctx, ddr_base+4*i, pattern[i]);
	}
	printf("done\n");

	if (argc >= 4) {
		sscanf(argv[3], "%d", &delay);
		printf("waiting for %d second(s)...", delay);
		fflush(stdout);
		sleep(delay);
		printf("done\n");
	}

	printf("Dumping data sequence...\n");
	for (i = 0; i < kPatternSize; i++) {
		if ((i % kDumpWidth) == 0) {
			printf("%08x | ", ddr_base+4*i);
		}

		expected_value = pattern[i];

		for (int j = 3; j >= 0; j--) {
			printf("%02x", ((uint8_t*)(&expected_value))[j]);
		}

		if ((i % kDumpWidth) == kDumpWidth-1) {
			printf("\n");
		} else {
			printf(" ");
		}
	}
	printf("\n");

	printf("Reading data sequence...\n");
	for (i = 0; i < kPatternSize; i++) {
		if ((i % kDumpWidth) == 0) {
			printf("%08x | ", ddr_base+4*i);
		}

		read_value = gram_read(&ctx, ddr_base+4*i);
		expected_value = pattern[i];

		for (int j = 3; j >= 0; j--) {
			if (((uint8_t*)(&read_value))[j] != ((uint8_t*)(&expected_value))[j]) {
				printf("\033[0;31m%02x\033[0m", ((uint8_t*)(&read_value))[j]);
				miss++;
			} else {
				printf("\033[0;32m%02x\033[0m", ((uint8_t*)(&read_value))[j]);
			}
		}

		if ((i % kDumpWidth) == kDumpWidth-1) {
			printf("\n");
		} else {
			printf(" ");
		}
	}

	printf("Burstdet %d-%d\n", gram_read_burstdet(&ctx, 0), gram_read_burstdet(&ctx, 1));

	printf("Memtest miss score (lowest is better): %d/100\n", (miss/4)*100/kPatternSize);

	close(serial_port);

	return EXIT_SUCCESS;
}
