#!/bin/bash
# run_p87.sh <NAME> <DD.MM.YY> <out.img>
NAME="$1"; DATE="$2"; OUT="$3"
python3 - "$NAME" "$DATE" <<'PY'
import sys
name, date = sys.argv[1].encode(), sys.argv[2].encode()
assert len(name) <= 13 and len(date) <= 12
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = name.ljust(13)
d[0x60:0x6C] = date.ljust(12)
open('/home/hamidi/code/knit/dosrun/135HQ.DEF','wb').write(bytes(d))
PY
cp exp/b800h96.tif dosrun/135HQ.TIF
cp samples/formatted_empty_image dosrun/floppy.img
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd dosrun
DISPLAY=:99 setsid dosbox-x -conf dosbox-x.conf > /tmp/p87-dx.log 2>&1 &
sleep 9
DISPLAY=:99 xdotool key Return; sleep 2.5
DISPLAY=:99 xdotool key w; sleep 2.5
DISPLAY=:99 xdotool key Return; sleep 3
DISPLAY=:99 xdotool key Return; sleep 3
python3 - <<'PY'
import time
for _ in range(40):
    time.sleep(2)
    d = open('/home/hamidi/code/knit/dosrun/floppy.img','rb').read()
    if d.count(b'Copyright (C) KARL MAYER') >= 2 and b'MASCHINENTYP' in d:
        break
PY
sleep 25
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd .. && cp dosrun/floppy.img "$OUT"
