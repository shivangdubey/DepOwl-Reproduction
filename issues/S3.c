/* CPython Modules/_sqlite/cursor.c: checks sqlite3_stmt_readonly() (SQLite >= 3.7.4) */
#include <sqlite3.h>
int main(void) { sqlite3 *db; sqlite3_stmt *st; sqlite3_open(":memory:", &db); sqlite3_prepare_v2(db, "select 1", -1, &st, 0);
  int ro = sqlite3_stmt_readonly(st); sqlite3_finalize(st); sqlite3_close(db); return !ro; }
