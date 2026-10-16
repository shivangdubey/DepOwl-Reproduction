/* tclsqlite.c: statement counters via sqlite3_stmt_status() (SQLite >= 3.6.0) */
#include <sqlite3.h>
int main(void) { sqlite3 *db; sqlite3_stmt *st; sqlite3_open(":memory:", &db); sqlite3_prepare_v2(db, "select 1", -1, &st, 0);
  int n = sqlite3_stmt_status(st, SQLITE_STMTSTATUS_FULLSCAN_STEP, 0); sqlite3_finalize(st); sqlite3_close(db); return n; }
