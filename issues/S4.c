/* WebKitGTK platform/sql/SQLiteDatabase.cpp: error text via sqlite3_errstr() (SQLite >= 3.7.15) */
#include <sqlite3.h>
#include <stdio.h>
int main(void) { puts(sqlite3_errstr(SQLITE_BUSY)); return 0; }
