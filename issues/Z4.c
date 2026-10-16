/* libpng 1.6.40 pngrutil.c: disables adler32 checking via inflateValidate() (zlib >= 1.2.9) */
#include <zlib.h>
#include <string.h>
int main(void) { z_stream s; memset(&s, 0, sizeof s); if (inflateInit(&s) != Z_OK) return 1; int r = inflateValidate(&s, 0); inflateEnd(&s); return r; }
