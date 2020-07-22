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

	return ntohl(reply);
}

int gram_write(struct gramCtx *ctx, void *addr, uint32_t value) {
	uint8_t commands[10] = { 0x01, 0x01 };
	int sent;

	*(uint32_t*)(commands+2) = htonl((uint32_t)addr >> 2);
	*(uint32_t*)(commands+6) = htonl(value);

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
	uint32_t pattern[128];
	const int kDumpWidth = 8;
	size_t i;

	struct gramProfile profile = {0,0};

	if (argc != 3) {
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
	gram_init(&ctx, (void*)0x10000000, (void*)0x00009000, (void*)0x00008000);
	gram_load_calibration(&ctx, &profile);
	printf("done\n");

	srand(time(NULL));
	for (i = 0; i < 128; i++) {
		pattern[i] = rand();
	}

	printf("memtest... \n");
	volatile uint32_t ddr_base = 0x10000000;

	printf("Writing data sequence...");
	for (i = 0; i < 128; i++) {
		gram_write(&ctx, ddr_base+4*i, pattern[i]);
	}
	printf("done\n");

	printf("Reading data sequence...\n");
	for (i = 0; i < 128; i++) {
		if ((i % kDumpWidth) == 0) {
			printf("%08x | ", ddr_base+4*i);
		}

		read_value = gram_read(&ctx, ddr_base+4*i);
		expected_value = pattern[i];

		for (int j = 3; j >= 0; j--) {
			if (((uint8_t*)(&read_value))[j] != ((uint8_t*)(&expected_value))[j]) {
				printf("\033[0;31m%02x\033[0m", ((uint8_t*)(&read_value))[j]);
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

	close(serial_port);

	return EXIT_SUCCESS;
}
