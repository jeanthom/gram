OUTPUT_FORMAT("elf32-littleriscv")
ENTRY(_start)

MEMORY
{
	rom : ORIGIN = 0x00007000, LENGTH = 0x1000
	ram : ORIGIN = 0x00004000, LENGTH = 0x1000
}

SECTIONS
{
	.text :
	{
		_ftext = .;
		*entry*.o(.text)
		*(.text .stub .text.* .gnu.linkonce.t.*)
		_etext = .;
	} > rom

	.rodata :
	{
		. = ALIGN(8);
		_frodata = .;
		*(.rodata .rodata.* .gnu.linkonce.r.*)
		*(.rodata1)

		/* Make sure the file is aligned on disk as well
		   as in memory; CRC calculation requires that. */
		FILL(0);
		. = ALIGN(8);
		_erodata = .;
	} > rom

	.bss :
	{
		. = ALIGN(8);
		_fbss = .;
		*(.dynsbss)
		*(.sbss .sbss.* .gnu.linkonce.sb.*)
		*(.scommon)
		*(.dynbss)
		*(.bss .bss.* .gnu.linkonce.b.*)
		*(COMMON)
		. = ALIGN(8);
		_ebss = .;
		_end = .;
	} > ram

	/DISCARD/ :
	{
		*(.eh_frame)
		*(.comment)
		*(.data .data.* .gnu.linkonce.d.*)
		*(.data1)
		*(.sdata .sdata.* .gnu.linkonce.s.*)
	}
}

PROVIDE(_fstack = ORIGIN(ram) + LENGTH(ram) - 8);
