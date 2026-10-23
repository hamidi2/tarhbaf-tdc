#!/bin/bash
# یک دور: TIF را بده، IMG بگیر (autotype روی :99)
T="$1"; OUT="$2"
cp "$T" ~/code/knit/dosrun/135HQ.TIF
cp ~/code/knit/samples/formatted_empty_image ~/code/knit/dosrun/floppy.img
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cd ~/code/knit/dosrun && DISPLAY=:99 setsid dosbox-x -conf dosbox-x.conf > /tmp/cal-dx.log 2>&1 &
sleep 8
DISPLAY=:99 xdotool key Return; sleep 2.5
DISPLAY=:99 xdotool key w; sleep 2.5
DISPLAY=:99 xdotool key Return; sleep 3
DISPLAY=:99 xdotool key Return; sleep 3
# انتظار برای نوشتن کامل
python3 - <<'PY'
import time
d = '/home/hamidi/code/knit/dosrun/floppy.img'
for _ in range(45):
    time.sleep(2)
    if open(d,'rb').read().count(b'Copyright (C) KARL MAYER') >= 2:
        break
PY
pkill -9 -x dosbox-x 2>/dev/null; sleep 1
cp ~/code/knit/dosrun/floppy.img "$OUT"
