#ifndef GRAM_H
#define GRAM_H

enum GramError {
	GRAM_ERR_NONE = 0,
	GRAM_ERR_UNDOCUMENTED,
	GRAM_ERR_MEMTEST,
	
};

int gram_init(void);
int gram_memtest(void);

#endif /* GRAM_H */
