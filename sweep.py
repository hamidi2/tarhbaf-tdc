#!/usr/bin/env python3
"""Width/height sweep: for each TIF, run the autotype-driven PC-CONV write in a
fresh dosbox-x, then extract p87 + LAENGE via the catalog (scatter-tolerant)."""
import os, shutil, subprocess, sys, time

sys.path.insert(0, '/home/hamidi/code/knit')
from karlmayer_tdc import (BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks,
                           parse_params)

HOME = '/home/hamidi'
DOS = f'{HOME}/code/knit/dosrun'
EXP = f'{HOME}/code/knit/exp'
EMPTY = f'{HOME}/code/knit/samples/formatted_empty_image'

def extract(img):
    d = open(img, 'rb').read()
    recs = parse_catalog(d)
    if not recs:
        return None
    mb = file_blocks(recs, 'MUSTER')
    lb = file_blocks(recs, 'LAENGE')
    lblk = d[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
    ci = lblk.find(COPYRIGHT_SIG)
    # param: search for the header text; it may be scattered, so try catalog order first
    data = b''.join(d[b*BLOCK:(b+1)*BLOCK] for b in mb)
    e = data.find(b'\r\n\x00')
    par = None
    if 0 < e < 200:
        par = data[e+3:e+3+90]
    if par is None or int.from_bytes(par[8:10], 'big') == 0:
        # scattered: find "MASCHINENTYP :JACQUARD" contiguously anywhere
        i = d.find(b'MASCHINENTYP :JACQUARD')
        if i >= 0:
            e2 = d.find(b'\r\n\x00', i)
            par = d[e2+3:e2+3+90]
    if par is None:
        return None
    p = parse_params(par)
    return dict(w=p['width_px'], h=p['height'], rows=p['rows_this_disk'],
                p87=par[87], laenge=ci, first16=lblk[:16].hex(' '),
                chk=par[88:90].hex())

cases = sys.argv[1:] or ['w800', 'w1015', 'w1648h512', 'white']
for name in cases:
    src = f'{EXP}/{name}.tif'
    shutil.copy(src, f'{DOS}/135HQ.TIF')
    shutil.copy(EMPTY, f'{DOS}/floppy.img')
    subprocess.run(['pkill', '-9', '-x', 'dosbox-x'], check=False)
    time.sleep(1)
    with open('/tmp/sweep-dosbox.log', 'w') as lg:
        p = subprocess.Popen(['dosbox-x', '-conf', f'{DOS}/dosbox-x.conf'],
                             stdout=lg, stderr=lg,
                             env={**os.environ, 'DISPLAY': ':99'},
                             start_new_session=True)
    time.sleep(9)
    def key(k, d=0.4):
        subprocess.run(['xdotool', 'key', k], check=False)
        time.sleep(d)
    key('Return', 2); key('w', 2); key('Return', 3)
    done = False
    for _ in range(45):
        time.sleep(2)
        dd = open(f'{DOS}/floppy.img', 'rb').read()
        if dd.count(COPYRIGHT_SIG) >= 2:
            done = True
            break
    res = {'done': done}
    if done:
        r = extract(f'{DOS}/floppy.img')
        if r and r.get('w', -1) not in (-1, 0):
            res = r
        else:
            lbblks = [b for rec in parse_catalog(dd) if rec['name'].startswith('LAENGE')
                      for b in rec['blocks']]
            if lbblks:
                lblk = dd[lbblks[0]*BLOCK:(lbblks[0]+1)*BLOCK]
                res = {'laenge': lblk.find(COPYRIGHT_SIG), 'first8': lblk[:8].hex(' ')}
    shutil.copy(f'{DOS}/floppy.img', f'{EXP}/sw_{name}.img')
    print(f"{name:12} -> {res}", flush=True)
    subprocess.run(['pkill', '-9', '-x', 'dosbox-x'], check=False)
    time.sleep(1)
print("sweep done")
