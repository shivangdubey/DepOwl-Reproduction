/* FreeRADIUS rlm_sql_sqlite: registers functions with sqlite3_create_function_v2() (SQLite >= 3.7.3) */
#include <sqlite3.h>
static void f(sqlite3_context *c, int n, sqlite3_value **v) { sqlite3_result_int(c, 1); }
int main(void) { sqlite3 *db; sqlite3_open_v2(":memory:", &db, SQLITE_OPEN_READWRITE, 0);
  int rc = sqlite3_create_function_v2(db, "f", 0, SQLITE_UTF8, 0, f, 0, 0, 0); sqlite3_close(db); return rc; }
