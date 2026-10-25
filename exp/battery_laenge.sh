#!/bin/bash
# باتری جاروب ابعاد برای مدل LAENGE=f(w,h): هر دور یک TIF با ابعاد تازه ساخته و می‌نویسد
cd /home/hamidi/code/knit
mkdir -p exp/la
python3 - <<'PY'
# TIF کنترل‌شدهٔ پایه (نیمه‌سفید/نیمه‌سیاه ساده) — محتوا مهم نیست
from PIL import Image
import numpy as np
def mk(w, h, path):
    a = np.zeros((h, w), dtype=np.uint8)
    a[:h//2] = 255
    Image.fromarray(a).convert('1').save(path)
PY
R() {  # R <W> <H>
W="$1"; H="$2"
python3 - "$W" "$H" <<'PY'
import sys
from PIL import Image
import numpy as np
w, h = int(sys.argv[1]), int(sys.argv[2])
a = np.zeros((h, w), dtype=np.uint8)
a[:h//2] = 255
Image.fromarray(a).convert('1').save('/home/hamidi/code/knit/exp/la/t.tif')
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = b'AAA'.ljust(13)
d[0x60:0x6C] = b'25.10.26'.ljust(12)
open('/home/hamidi/code/knit/dosrun/135HQ.DEF','wb').write(bytes(d))
PY
cp exp/la/t.tif dosrun/135HQ.TIF
cp samples/formatted_empty_image dosrun/floppy.img
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
( cd dosrun && DISPLAY=:99 setsid dosbox-x -conf dosbox-x.conf > /tmp/p87-dx.log 2>&1 & )
sleep 9
DISPLAY=:99 xdotool key Return; sleep 2.5
DISPLAY=:99 xdotool key w; sleep 2.5
DISPLAY=:99 xdotool key Return; sleep 3
DISPLAY=:99 xdotool key Return; sleep 3
for j in $(seq 1 50); do
  sleep 3
  python3 -c "d=open('/home/hamidi/code/knit/dosrun/floppy.img','rb').read(); exit(0 if d.count(b'Copyright (C) KARL MAYER')>=2 else 1)" && break
done
sleep 15
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cp dosrun/floppy.img "exp/la/w${W}h${H}.img"
echo "w=$W h=$H done"
}
for H in 128 192 256 320 448 512 768; do R 1648 "$H"; done
for H in 128 192 256 320 448 512; do R 800 "$H"; done
for H in 128 256 512; do R 1016 "$H"; done
R 1000 256
R 1024 256
R 1648 96
echo ALL-DONE
