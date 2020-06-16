# libgram, the C companion for gram

libgram is the C library for gram core initialization and memory testing.

## HowTo

Build libgram with make. In your firmware:

```C
#include <gram.h>

int main(void) {
	struct gramCtx ctx;
	int err = gram_init(&ctx, 0x10000000, 0x00006000, 0x00005000);

	return 0;
}
```

Link it to this library and you should be good to go!

## Error handling

```
GRAM_ERR_NONE: No error happened (hardcoded to zero)
GRAM_ERR_UNDOCUMENTED: Undocumented error, shame on us lazy coders (take a look at the code)
```

## Using libgram when you can't directly access the bus

Compile libgram with `CFLAGS="-DGRAM_RW_FUNC"` (run `make clean` beforehand) then define the following functions:

```c
uint32_t gram_read(struct gramCtx *ctx, void *addr);
int gram_write(struct gramCtx *ctx, void *addr, uint32_t value);
```

If you want to use the default compiler on your computer, use `CFLAGS="-DGRAM_RW_FUNC" make TRIPLE=""`.
