/* MacPorts registry2.0: compiles statements with sqlite3_prepare_v2() (SQLite >= 3.3.9) */
#include <sqlite3.h>
int main(void) { sqlite3 *db; sqlite3_stmt *st; sqlite3_open(":memory:", &db);
  int rc = sqlite3_prepare_v2(db, "select 1", -1, &st, 0); sqlite3_finalize(st); sqlite3_close(db); return rc; }
