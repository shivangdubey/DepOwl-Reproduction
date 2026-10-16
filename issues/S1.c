/* fossil 2.3: compiles statements with sqlite3_prepare_v3() (SQLite >= 3.20.0) */
#include <sqlite3.h>
int main(void) { sqlite3 *db; sqlite3_stmt *st; sqlite3_open(":memory:", &db);
  int rc = sqlite3_prepare_v3(db, "select 1", -1, 0, &st, 0); sqlite3_finalize(st); sqlite3_close(db); return rc; }
