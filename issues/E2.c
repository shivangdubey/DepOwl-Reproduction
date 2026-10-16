/* CPython Modules/pyexpat.c: seeds expat's hash with XML_SetHashSalt() (expat >= 2.1.0) */
#include <expat.h>
int main(void) { XML_Parser p = XML_ParserCreate(NULL); XML_SetHashSalt(p, 42); XML_ParserFree(p); return 0; }
