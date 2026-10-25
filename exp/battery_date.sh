#!/bin/bash
# باتری p87 روی تاریخ سیستم DOS با faketime (نام ثابت AAA)
cd /home/hamidi/code/knit
LIB=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1
R() {  # R <YYYY-MM-DD HH:MM:SS> <out.img>
FT="$1"; OUT="$2"
python3 - <<'PY'
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = b'AAA'.ljust(13)
open('/home/hamidi/code/knit/dosrun/135HQ.DEF','wb').write(bytes(d))
PY
cp exp/b800h96.tif dosrun/135HQ.TIF
cp samples/formatted_empty_image dosrun/floppy.img
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd dosrun
DISPLAY=:99 FAKETIME="@${FT}" LD_PRELOAD=$LIB setsid dosbox-x -conf dosbox-x.conf > /tmp/p87-dx.log 2>&1 &
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
}
i=0
for d in 01 02 15 28 31; do i=$((i+1)); T="2026-10-$d 10:00:00"; O="exp/p87bat/ft_10_$d_26.img"; echo "== [$i] $T"; R "$T" "$O"; python3 exp/get_p87.py "$O"; done
for m in 01 02 03 06 09 12; do i=$((i+1)); T="2026-$m-10 10:00:00"; O="exp/p87bat/ft_${m}_10_26.img"; echo "== [$i] $T"; R "$T" "$O"; python3 exp/get_p87.py "$O"; done
for y in 2000 2003 1999; do i=$((i+1)); T="$y-10-10 10:00:00"; O="exp/p87bat/ft_10_10_$y.img"; echo "== [$i] $T"; R "$T" "$O"; python3 exp/get_p87.py "$O"; done
echo "== [v] 2003-05-21 sanity"; R "2003-05-21 10:00:00" "exp/p87bat/ft_05_21_03.img"; python3 exp/get_p87.py exp/p87bat/ft_05_21_03.img
echo DONE
