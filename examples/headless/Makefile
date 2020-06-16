OBJS := main.o

CFLAGS += -g -I../../libgram/include/

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

headless: $(OBJS) ../../libgram/libgram.a
	$(CC) $(LDFLAGS) $(OBJS) ../../libgram/libgram.a -o $@

clean:
	rm -f $(OBJS)
	rm -f headless
