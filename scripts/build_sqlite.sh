#!/bin/bash
R=${REPRO:-$(cd "$(dirname "$0")/.." && pwd)}; mkdir -p "$R/logs"
# build one sqlite tag (default compile options) as libsqlite3.so.0 with debug info
tag=$1; ver=${tag#version-}
W=$R/work/sqlite/$ver; P=$R/build/sqlite/$ver
[ -f $P/.ok ] && exit 0
export PATH=$R/tools/tcl/bin:$PATH; [ -x $R/tools/tcl/bin/tclsh8.6 ] && ln -sf tclsh8.6 $R/tools/tcl/bin/tclsh
rm -rf $W $P && mkdir -p $W/src $W/bld $P/lib $P/include && git -C $R/src/sqlite archive $tag | tar -x -C $W/src
chmod +x $W/src/configure $W/src/install-sh $W/src/config.* $W/src/ltmain.sh 2>/dev/null
cd $W/bld
{
  [ -n "$REGEN" ] && (cd ../src && autoconf 2>&1 | tail -1)
  echo "$ver" > ../src/VERSION.tmp
  [ -f ../src/manifest ] || echo "C unknown" > ../src/manifest
  [ -f ../src/manifest.uuid ] || echo "0000000000000000000000000000000000000000" > ../src/manifest.uuid
  CFLAGS="-g -O0 -fcommon -Wno-error -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types" ../src/configure --disable-tcl --disable-readline --enable-shared 2>&1 | tail -2
  if make sqlite3.c; then
     gcc -g -O0 -fPIC -fcommon -shared -Wl,-soname,libsqlite3.so.0 -o libsqlite3.so.$ver sqlite3.c -lpthread -ldl -lm \
       -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types && echo BUILT-AMALG
  fi
  if [ ! -f libsqlite3.so.$ver ]; then
     make libsqlite3.la && cp $(ls .libs/libsqlite3.so.0.* | head -1) libsqlite3.so.$ver && echo BUILT-LIBTOOL
  fi
} > $R/logs/sqlite-$ver.log 2>&1
cp libsqlite3.so.$ver $P/lib/ 2>/dev/null && ln -sf libsqlite3.so.$ver $P/lib/libsqlite3.so.0 && ln -sf libsqlite3.so.$ver $P/lib/libsqlite3.so && cp sqlite3.h $P/include/ 2>/dev/null
case $ver in 3.6.11|3.40.1) mkdir -p $P/src && cp $W/bld/sqlite3.c $P/src/ ;; esac   # sources for the S8/S9 compile-option variants in rq1.py
[ -f $P/lib/libsqlite3.so.$ver ] && rm -rf $W
[ -f $P/lib/libsqlite3.so.$ver ] && touch $P/.ok && echo "ok $ver $(grep -o 'BUILT-.*' $R/logs/sqlite-$ver.log)" || echo "FAIL $ver"
