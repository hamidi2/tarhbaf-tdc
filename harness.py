#!/usr/bin/env python3
"""Full end-to-end validation harness (runs on invisible display :99).

For each TIF:
  1. PC-CONV Write  -> IMG_theirs        (drives dosbox-x via keys)
  2. our builder    -> IMG_ours          (same config pieces, same name/date)
  3. PC-CONV Read of IMG_theirs -> expect clean, JACQ1.TIF == doubled TIF
  4. PC-CONV Read of IMG_ours  -> expect clean, JACQ1.TIF == doubled TIF
  5. content compare IMG_ours vs IMG_theirs (layout-insensitive)
Results appended to /tmp/harness.log
"""
import os, shutil, subprocess, sys, time, struct

sys.path.insert(0, '/home/hamidi/code/knit')
from karlmayer_tdc import (BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks,
                           parse_params, build_disk)
from PIL import Image

HOME = '/home/hamidi'
DOS = f'{HOME}/code/knit/dosrun'
CASES_DIR = f'{HOME}/code/knit/harness'
EMPTY = f'{HOME}/code/knit/samples/formatted_empty_image'

def key(k, d=0.5):
    subprocess.run(['xdotool', 'key', k], check=False)
    time.sleep(d)

def focus():
    out = subprocess.run(['xdotool', 'search', '--name', 'PC-CONV'],
                         capture_output=True, text=True)
    wids = out.stdout.split()
    if wids:
        subprocess.run(['xdotool', 'windowfocus', wids[-1]], check=False)
        time.sleep(0.4)
        return wids[-1]
    return None

def launch():
    subprocess.run(['pkill', '-9', '-x', 'dosbox-x'], check=False)
    time.sleep(1)
    lg = open('/tmp/harness-dosbox.log', 'a')
    subprocess.Popen(['dosbox-x', '-conf', f'{DOS}/dosbox-x.conf'],
                     stdout=lg, stderr=subprocess.STDOUT,
                     env={**os.environ, 'DISPLAY': ':99'}, start_new_session=True)
    time.sleep(9)

def shot_red(tag):
    wid = focus()
    if not wid: return 0
    subprocess.run(['xwd', '-id', wid, '-silent', '-out', f'/tmp/{tag}.xwd'], check=False)
    try:
        data = open(f'/tmp/{tag}.xwd', 'rb').read()
    except OSError:
        return -1
    hdr = struct.unpack('>25I', data[:100])
    w, h, bpp, bpl = hdr[4], hdr[5], hdr[11], hdr[12]
    off = hdr[0] + hdr[19]*12
    raw = b''.join(data[off+y*bpl: off+y*bpl+w*(bpp//8)] for y in range(h))
    img = Image.frombytes('RGB', (w, h), raw, 'raw', 'BGRX' if bpp == 32 else 'BGR')
    img.save(f'/tmp/{tag}.png')
    px = img.load()
    return sum(1 for y in range(0, h, 3) for x in range(0, w, 3)
               if px[x, y][0] > 170 and px[x, y][1] < 90 and px[x, y][2] < 90)

def write_flow():
    launch(); focus()
    key('Return', 2.5)             # license
    key('w', 2.5)                  # write floppy
    key('Return', 3)               # confirm 135HQ.DEF
    # wait for completion: two copyright signatures = header+laenge trailers present
    for _ in range(45):
        time.sleep(2)
        d = open(f'{DOS}/floppy.img', 'rb').read()
        if d.count(COPYRIGHT_SIG) >= 2:
            return True
    return shot_red('hw') < 30      # no error box?

def read_flow(tag):
    launch(); focus()
    key('Return', 2.5)             # license
    key('r', 2.5)                  # read floppy
    key('Return', 3)               # Ok
    key('Return', 3)               # insert-first-floppy confirm
    ok = False
    for _ in range(30):
        time.sleep(2)
        if os.path.exists(f'{DOS}/JACQ1.TIF'):
            ok = True
            break
        r = shot_red(f'{tag}-err')
        if r > 30:
            return False           # error dialog (e.g. #140/#143)
    if ok:
        time.sleep(2)
    return ok

def pieces_from(path):
    d = open(path, 'rb').read()
    recs = parse_catalog(d)
    mb = file_blocks(recs, 'MUSTER')
    lb = file_blocks(recs, 'LAENGE')
    data = b''.join(d[x*BLOCK:(x+1)*BLOCK] for x in mb)
    e = data.find(b'\r\n\x00')
    par = data[e+3:e+3+90]
    p = parse_params(par)
    dbytes = p['width_bits'] // 8
    pitch = (dbytes + 1) // 2 * 2 + 2
    ce = e + 3 + 90 + p['rows_this_disk'] * pitch
    trailer = data[ce:ce + 1868]
    lblk = d[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
    laenge = lblk[:lblk.find(COPYRIGHT_SIG)]
    nm = data[:e+2].split(b'\r\n')[1].decode('latin1').split(':')[1].strip()
    dt = data[:e+2].split(b'\r\n')[2].decode('latin1').split(':')[1].strip()
    return dict(param=bytes(par[:88]), laenge=laenge, trailer=trailer,
                name=nm, date=dt, w=p['width_px'], wbits=p['width_bits'],
                h=p['height'], rows=p['rows_this_disk'])

def build_like(cfg, tifpath, outpath):
    im = Image.open(tifpath)
    W, H0 = im.size
    H = H0
    while H < 192: H *= 2
    wbits = (W + 7) // 8 * 8
    dbytes = wbits // 8
    tifb = im.tobytes(); trb = (W + 7) // 8
    mask = (1 << (8 - (((W - 1) % 8) + 1))) - 1
    rows = []
    for r in range(H):
        src = r * H0 // H
        row = bytearray(tifb[src*trb:(src+1)*trb]); row += bytes(dbytes - len(row))
        row[trb-1] |= mask
        rows.append(bytes(row))
    t = {'param': cfg['param'], 'laenge': cfg['laenge'], 'trailer': cfg['trailer']}
    out = build_disk(rows, wbits, W, H, cfg['name'], cfg['date'], t,
                     ndisks=1, thisdisk=1, rows_this_disk=H,
                     disk1_rows=H, disk2_start=0, disk2_rows=0,
                     disk_capacity_blocks=2877)
    open(outpath, 'wb').write(out)
    return W, H0, H

def content_of(path):
    d = open(path, 'rb').read()
    recs = parse_catalog(d)
    mb = file_blocks(recs, 'MUSTER')
    data = b''.join(d[x*BLOCK:(x+1)*BLOCK] for x in mb)
    e = data.find(b'\r\n\x00')
    par = data[e+3:e+3+90]
    p = parse_params(par)
    dbytes = p['width_bits'] // 8
    pitch = (dbytes + 1) // 2 * 2 + 2
    ce = e + 3 + 90 + p['rows_this_disk'] * pitch
    lb = file_blocks(recs, 'LAENGE')
    lblk = d[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
    return data[e+3+90:ce], par, data[ce:ce+1868], lblk[:lblk.find(COPYRIGHT_SIG)]

cases = sys.argv[1:]
log = open('/tmp/harness.log', 'a')
def say(msg):
    print(msg, flush=True)
    log.write(msg + '\n'); log.flush()

def restart_xvfb():
    subprocess.run(['pkill', '-x', 'Xvfb'], check=False)
    time.sleep(2)
    subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1024x768x24'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

for name in cases:
    tif = f'{CASES_DIR}/{name}.tif'
    say(f'=== {name}')
    restart_xvfb()
    # 1) PC-CONV write
    shutil.copy(tif, f'{DOS}/135HQ.TIF')
    shutil.copy(EMPTY, f'{DOS}/floppy.img')
    wok = write_flow()
    if not wok:
        say(f'{name}: WRITE FAILED'); continue
    theirs = f'{CASES_DIR}/{name}-theirs.img'
    shutil.copy(f'{DOS}/floppy.img', theirs)
    cfg = pieces_from(theirs)
    # 2) our build (same name/date/config)
    ours = f'{CASES_DIR}/{name}-ours.img'
    W, H0, H = build_like(cfg, tif, ours)
    # 3) read theirs
    shutil.copy(theirs, f'{DOS}/floppy.img')
    rt = read_flow(f'{name}-rt')
    shutil.copy(f'{DOS}/JACQ1.TIF', f'{CASES_DIR}/{name}-rt-theirs.tif') if os.path.exists(f'{DOS}/JACQ1.TIF') else None
    # 4) read ours
    shutil.copy(ours, f'{DOS}/floppy.img')
    ro = read_flow(f'{name}-ro')
    shutil.copy(f'{DOS}/JACQ1.TIF', f'{CASES_DIR}/{name}-rt-ours.tif') if os.path.exists(f'{DOS}/JACQ1.TIF') else None
    # 5) content compare
    try:
        co, po, tro, lo = content_of(ours)
        ct, pt, trt, lt = content_of(theirs)
        same_c = co == ct
        same_l = lo == lt and len(lo) == len(lt)
        same_p = all(po[i] == pt[i] for i in range(88))
    except Exception as ex:
        same_c = same_l = same_p = f'ERR {ex}'
    say(f'{name}: write={wok} read_theirs={rt} read_ours={ro} '
        f'content_same={same_c} laenge_same={same_l} params_same(excl-chk)={same_p} '
        f'dims={W}x{H0}->{H}')
say('HARNESS DONE')
