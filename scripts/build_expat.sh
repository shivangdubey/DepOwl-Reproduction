#!/bin/bash
R=${REPRO:-$(cd "$(dirname "$0")/.." && pwd)}; mkdir -p "$R/logs"
# build one expat tag (2.x, soname libexpat.so.1) with debug info, default features
tag=$1; ver=$(echo ${tag#R_} | tr _ .)
W=$R/work/expat/$ver; P=$R/build/expat/$ver
[ -f $P/.ok ] && exit 0
rm -rf $W $P && mkdir -p $W $P/lib $P/include && git -C $R/src/libexpat archive $tag expat/lib | tar -x -C $W
cd $W/expat/lib
cat > expat_config.h <<'H'
#define BYTEORDER 1234
#define HAVE_MEMMOVE 1
#define HAVE_GETRANDOM 1
#define HAVE_SYSCALL_GETRANDOM 1
#define XML_NS 1
#define XML_DTD 1
#define XML_GE 1
#define XML_CONTEXT_BYTES 1024
#define XML_DEV_URANDOM 1
#define HAVE_UNISTD_H 1
#define HAVE_FCNTL_H 1
#define HAVE_STDINT_H 1
#define HAVE_STRING_H 1
#define HAVE_STDLIB_H 1
#define STDC_HEADERS 1
H
VIS=""; grep -q visibility expat_external.h && VIS="-DXML_ENABLE_VISIBILITY=1 -fvisibility=hidden"
{ gcc -g -O0 -fPIC -fcommon -I. -DHAVE_EXPAT_CONFIG_H $VIS -shared -Wl,-soname,libexpat.so.1 \
     -Wl,--no-undefined -o libexpat.so.$ver $(for f in xcs.c xmlparse.c xmltok.c xmlrole.c random_dev_urandom.c random_getrandom.c; do [ -f $f ] && echo $f; done) -lm ; } > $R/logs/expat-$ver.log 2>&1
cp libexpat.so.$ver $P/lib/ 2>/dev/null && ln -sf libexpat.so.$ver $P/lib/libexpat.so.1 && ln -sf libexpat.so.$ver $P/lib/libexpat.so && cp expat.h expat_external.h $P/include/
n=$(nm -D --defined-only $P/lib/libexpat.so.$ver 2>/dev/null | grep -c " T XML_")
[ -f $P/lib/libexpat.so.$ver ] && rm -rf $W
[ -f $P/lib/libexpat.so.$ver ] && touch $P/.ok && echo "ok $ver XML_funcs=$n" || echo "FAIL $ver"
