/* vcftools vcf_file.cpp: enlarges the gz read buffer with gzbuffer() */
#include <zlib.h>
int main(int c, char **v) { gzFile f = gzopen(c > 1 ? v[1] : "/dev/null", "rb"); if (!f) return 1; gzbuffer(f, 128 * 1024); gzclose(f); return 0; }
