#!/bin/bash
# باتری p87 روی تاریخ سیستم DOS با autoexec DATE mm-dd-yyyy (نام ثابت AAA)
cd /home/hamidi/code/knit
R() {  # R <MM-DD-YYYY> <dd.mm.yy-for-DEF> <out.img>
DS="$1"; DEFD="$2"; OUT="$3"
python3 - "$DEFD" <<'PY'
import sys
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = b'AAA'.ljust(13)
d[0x60:0x6C] = sys.argv[1].encode().ljust(12)
open('/home/hamidi/code/knit/dosrun/135HQ.DEF','wb').write(bytes(d))
PY
cp exp/b800h96.tif dosrun/135HQ.TIF
cp samples/formatted_empty_image dosrun/floppy.img
sed "s/^PC-CONV.EXE$/DATE $DS\nPC-CONV.EXE/" dosrun/dosbox-x.conf > /tmp/p87d.conf
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd dosrun
DISPLAY=:99 setsid dosbox-x -conf /tmp/p87d.conf > /tmp/p87-dx.log 2>&1 &
sleep 9
DISPLAY=:99 xdotool key Return; sleep 2.5
DISPLAY=:99 xdotool key w; sleep 2.5
DISPLAY=:99 xdotool key Return; sleep 3
DISPLAY=:99 xdotool key Return; sleep 3
python3 - <<'PY'
import time
for _ in range(40):
    time.sleep(3)
    d = open('/home/hamidi/code/knit/dosrun/floppy.img','rb').read()
    if b'MASCHINENTYP' in d:
        break
PY
sleep 20
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd .. && cp dosrun/floppy.img "$OUT"
}
i=0
for d in 01 02 15 28 31; do i=$((i+1)); ds="10-$d-2026"; dd="$(echo $d | sed 's/^0//').10.26"; o="exp/p87bat/d2_10_$d_26.img"; echo "== [$i] $ds"; R "$ds" "$dd" "$o"; python3 exp/get_p87.py "$o"; done
for m in 01 02 03 06 09 12; do i=$((i+1)); ds="$m-10-2026"; mm=$(echo $m | sed 's/^0//'); dd="10.$mm.26"; o="exp/p87bat/d2_${m}_10_26.img"; echo "== [$i] $ds"; R "$ds" "$dd" "$o"; python3 exp/get_p87.py "$o"; done
for y in 2000 2003 1999 1980; do i=$((i+1)); ds="10-10-$y"; yy=${y#20}; yy=${yy#19}; [ "$y" = 1980 ] && yy=80; [ "$y" = 1999 ] && yy=99; dd="10.10.$yy"; o="exp/p87bat/d2_10_10_$y.img"; echo "== [$i] $ds"; R "$ds" "$dd" "$o"; python3 exp/get_p87.py "$o"; done
echo "== [v] sanity 05-21-2003"; R "05-21-2003" "21.05.03" "exp/p87bat/d2_05_21_03.img"; python3 exp/get_p87.py exp/p87bat/d2_05_21_03.img
echo DONE
