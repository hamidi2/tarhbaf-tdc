#!/bin/bash
# جاروب عرض برای مدل s(w) در len=(180+s*h) mod 2048 — دو ارتفاع 128 و 192 برای هر عرض
cd /home/hamidi/code/knit
R() {
W="$1"; H="$2"
python3 - "$W" "$H" <<'PY'
import sys
from PIL import Image
import numpy as np
w, h = int(sys.argv[1]), int(sys.argv[2])
a = np.zeros((h, w), dtype=np.uint8); a[:h//2] = 255
Image.fromarray(a).convert('1').save('/home/hamidi/code/knit/exp/la/t.tif')
d = bytearray(open('/home/hamidi/code/knit/testdata/135HQ.DEF','rb').read())
d[0x42:0x4F] = b'AAA'.ljust(13); d[0x60:0x6C] = b'25.10.26'.ljust(12)
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
for W in 256 384 512 640 768 896 1088 1152 1280 1536 1920 2048; do
  R "$W" 128; R "$W" 192
done
echo ALL-DONE
