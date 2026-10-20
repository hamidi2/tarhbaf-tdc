#!/bin/bash
# آماده‌سازی یک دور آزمایش:  round.sh <عرض>  — بعد از بستن DOSBox اجرا شود
W="$1"
cp ~/code/knit/exp/w$W.tif ~/code/knit/dosrun/135HQ.TIF
cp ~/code/knit/samples/formatted_empty_image ~/code/knit/dosrun/floppy.img
echo "دور $W آماده شد. حالا DOSBox را باز کن:  cd ~/code/knit/dosrun && dosbox-x -conf dosbox-x.conf"
echo "داخل DOSBox:  Enter (لایسنس) → W → Enter (تأیید DEF) → تا ۱۰۰٪ صبر کن، بعد بهم بگو."
