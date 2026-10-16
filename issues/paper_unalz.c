/* Paper Sec. IV-B / Table III example: unalz-0.65 reads zlib's CRC table as long */
#include <zlib.h>
int main(void) { long *CRC_TABLE = (long *)get_crc_table(); return CRC_TABLE[1] == 0; }
