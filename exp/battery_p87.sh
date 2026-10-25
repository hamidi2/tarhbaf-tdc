#!/bin/bash
# باتری آزمایش p87: جاروب کاراکترهای نام و مولفه‌های تاریخ
cd /home/hamidi/code/knit
mkdir -p exp/p87bat
i=0
run() { i=$((i+1)); echo "== [$i] $1 $2"; bash exp/run_p87.sh "$1" "$2" "exp/p87bat/$(printf %02d $i)_$(echo "$1" | tr -c 'A-Za-z0-9' '_')_${2//./-}.img" >> /tmp/p87bat.log 2>&1; python3 exp/get_p87.py "exp/p87bat/$(printf %02d $i)_$(echo "$1" | tr -c 'A-Za-z0-9' '_')_${2//./-}.img"; }

D=24.10.26
for c in B C D E F G H Z 0 1 9 _; do run "AA$c" "$D"; done
for c in B C Z 0;            do run "A${c}A" "$D"; done
for c in B Z 0;              do run "${c}AA" "$D"; done
for n in 111 999 000;        do run "$n" "$D"; done

for d in 01.10.26 19.01.26 19.12.26 19.10.27 19.10.00 29.10.26; do run "135HQ" "$d"; done
for d in 01.10.26 19.01.26 19.10.27; do run "AAA" "$d"; done
echo DONE
