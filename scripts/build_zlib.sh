#!/bin/bash
R=${REPRO:-$(cd "$(dirname "$0")/.." && pwd)}; mkdir -p "$R/logs"
# build one zlib tag with debug info into $R/build/zlib/<ver>
tag=$1; ver=${tag#v}
W=$R/work/zlib/$ver; P=$R/build/zlib/$ver
[ -f $P/.ok ] && exit 0
rm -rf $W $P && mkdir -p $W $P/lib $P/include && git -C $R/src/zlib archive $tag | tar -x -C $W
cd $W
{
  CFLAGS="-g -O0 -fPIC -fcommon -D_LARGEFILE64_SOURCE=1" ./configure --static --prefix=$P || CFLAGS="-g -O0 -fPIC -fcommon -D_LARGEFILE64_SOURCE=1" ./configure --prefix=$P
  make libz.a
  mkdir -p objs; make libz.a; mkdir -p aro && (cd aro && ar x ../libz.a)
  if [ -f zlib.map ] && gcc -shared -Wl,-soname,libz.so.1,--version-script,zlib.map -o libz.so.$ver aro/*.o; then echo "linked with version script"
  else gcc -shared -Wl,-soname,libz.so.1 -o libz.so.$ver aro/*.o && echo "linked WITHOUT version script"; fi
  cp libz.so.$ver $P/lib/ && ln -sf libz.so.$ver $P/lib/libz.so.1 && ln -sf libz.so.$ver $P/lib/libz.so
  cp zlib.h zconf.h $P/include/; [ -f zlibdefs.h ] && cp zlibdefs.h $P/include/
} > $R/logs/zlib-$ver.log 2>&1
[ -f $P/lib/libz.so.$ver ] && rm -rf $W
[ -f $P/lib/libz.so.$ver ] && touch $P/.ok && echo "ok $ver $(grep -o 'linked.*' $R/logs/zlib-$ver.log)" || echo "FAIL $ver"
