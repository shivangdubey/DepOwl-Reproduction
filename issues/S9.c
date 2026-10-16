/* font-manager libfontmanager: column provenance via sqlite3_column_origin_name() */
#include <sqlite3.h>
#include <stdio.h>
int main(void) { sqlite3 *db; sqlite3_stmt *st; sqlite3_open(":memory:", &db); sqlite3_exec(db, "create table t(a)", 0, 0, 0);
  sqlite3_prepare_v2(db, "select a from t", -1, &st, 0); const char *o = sqlite3_column_origin_name(st, 0); printf("%s\n", o ? o : "-");
  sqlite3_finalize(st); sqlite3_close(db); return 0; }
