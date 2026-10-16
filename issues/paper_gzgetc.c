/* Paper Sec. IV-C example: an application calling gzgetc() as a real function (built against zlib 1.2.5.1) */
#include <zlib.h>
#undef gzgetc
int gzgetc(gzFile);
int main(void) { gzFile f = gzopen("/dev/null", "rb"); if (!f) return 1; int ch = gzgetc(f); gzclose(f); return ch == -2; }
