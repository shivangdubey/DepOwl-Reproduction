/* spellfix.c loadable extension: allocates with sqlite3_malloc64() (SQLite >= 3.8.7) */
#include <sqlite3.h>
int main(void) { void *p = sqlite3_malloc64(64); sqlite3_free(p); return p == 0; }
