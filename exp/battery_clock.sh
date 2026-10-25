#!/bin/bash
# باتری p87 با تغییر ساعت میزبان — توالی صحیح: همهٔ setup در foreground
cd /home/hamidi/code/knit
mkdir -p exp/p87bat

R() {  # R <YYYY-MM-DD HH:MM:SS> <dd.mm.yy> <tag>
YMD="$1"; DEFD="$2"; TAG="$3"
python3 - "$DEFD" <<'PY'
import sys
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = b'AAA'.ljust(13)
d[0x60:0x6C] = sys.argv[1].encode().ljust(12)
open('/home/hamidi/code/knit/dosrun/135HQ.DEF','wb').write(bytes(d))
PY
cp exp/b800h96.tif dosrun/135HQ.TIF
cp samples/formatted_empty_image dosrun/floppy.img
T0=$(date +%s)
U0=$(cut -d. -f1 /proc/uptime)
sudo -n date -s "$YMD" >/dev/null
pkill -9 -x dosbox-x 2>/dev/null
sleep 1
( cd dosrun && DISPLAY=:99 setsid dosbox-x -conf dosbox-x.conf > /tmp/p87-dx.log 2>&1 & )
sleep 9
DISPLAY=:99 xdotool key Return; sleep 2.5
DISPLAY=:99 xdotool key w; sleep 2.5
DISPLAY=:99 xdotool key Return; sleep 3
DISPLAY=:99 xdotool key Return; sleep 3
conv=no
for j in $(seq 1 40); do
  sleep 3
  python3 -c "d=open('/home/hamidi/code/knit/dosrun/floppy.img','rb').read(); exit(0 if d.count(b'Copyright (C) KARL MAYER')>=2 else 1)" && { conv=yes; break; }
done
sleep 15
pkill -9 -x dosbox-x 2>/dev/null
sleep 1
U1=$(cut -d. -f1 /proc/uptime)
sudo -n date -s "@$((T0 + U1 - U0 + 3))" >/dev/null
cp dosrun/floppy.img "exp/p87bat/clk_$TAG.img"
echo "conv=$conv $TAG"
}

i=0
for spec in "2026-10-25 12:00:00|25.10.26|h12" "2026-10-25 23:00:00|25.10.26|h23" "2026-10-01 12:00:00|01.10.26|10_01" "2026-10-02 12:00:00|02.10.26|10_02" "2026-10-15 12:00:00|15.10.26|10_15" "2026-10-28 12:00:00|28.10.26|10_28" "2026-10-31 12:00:00|31.10.26|10_31" "2026-11-01 12:00:00|01.11.26|11_01" "2026-01-15 12:00:00|15.01.26|01_15" "2026-03-15 12:00:00|15.03.26|03_15" "2026-05-15 12:00:00|15.05.26|05_15" "2026-07-15 12:00:00|15.07.26|07_15" "2026-12-15 12:00:00|15.12.26|12_15" "2003-06-15 12:00:00|15.06.03|y2003" "2000-06-15 12:00:00|15.06.00|y2000" "1999-06-15 12:00:00|15.06.99|y1999" "2020-02-29 12:00:00|29.02.20|leap"; do
  YMD="${spec%%|*}"; rest="${spec#*|}"; DEFD="${rest%%|*}"; TAG="${rest#*|}"
  i=$((i+1)); echo "== [$i] $YMD"
  R "$YMD" "$DEFD" "$TAG"
  python3 exp/get_p87.py "exp/p87bat/clk_$TAG.img"
done
echo ALL-DONE
date
