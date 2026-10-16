/* PHP ext/sqlite3: enables extension loading with sqlite3_enable_load_extension() */
#include <sqlite3.h>
int main(void) { sqlite3 *db; sqlite3_open(":memory:", &db); int rc = sqlite3_enable_load_extension(db, 1); sqlite3_close(db); return rc; }
