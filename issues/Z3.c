/* PostgreSQL pg_dump compress_io.c cfgetc(): calls gzgetc(), a macro over gzgetc_() in these zlib headers */
#include <zlib.h>
int main(int c, char **v) { gzFile f = gzopen(c > 1 ? v[1] : "/dev/null", "rb"); if (!f) return 1; int ch = gzgetc(f); gzclose(f); return ch == -2; }
