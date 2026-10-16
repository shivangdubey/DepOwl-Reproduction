/* libxml2 (xmlIO.c) opening compressed input with large-file support: gzopen64 */
#define _LARGEFILE64_SOURCE 1
#include <zlib.h>
int main(int c, char **v) { gzFile f = gzopen64(c > 1 ? v[1] : "/dev/null", "rb"); if (f) gzclose(f); return 0; }
