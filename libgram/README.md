# libgram, the C companion for gram

libgram is the C library for gram core initialization.

## HowTo

Provide the CSV file from your LambdaSoC build to the Makefile:

```bash
make CSR_CSV_FILE=$SOC_BUILD/soc/soc_resources.csv
```

In your firmware:

```C
#include <gram.h>

int main(void) {
	int err = gram_init();

	/* insert something meaningful here */

	return 0;
}
```

Link it to this library and you should be good to go!

## Error handling

```
GRAM_ERR_NONE: No error happened (hardcoded to zero)
GRAM_ERR_UNDOCUMENTED: Undocumented error, shame on us lazy coders (take a look at the code)
GRAM_ERR_MEMTEST: Memtest failed
```
