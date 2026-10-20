# طرح‌باف (TDC Knitter)

**English:** A small, dependency-free Windows program that converts an image into a
1.44 MB floppy-disk image for **Karl Mayer TDC** jacquard knitting machines
(Textronic Design Center era software, ~1991). It replaces the original DOS
converter with a modern one-file `knitter.exe`: pick a picture, get a floppy
image you can write to a disk with any raw-image tool.

**فارسی:** برنامهٔ ویندوزی تک‌فایلی برای تبدیل تصویر به فلاپیِ دستگاه بافندگی
جاکوارد کارل مایر (نرم‌افزار TDC حدود ۱۹۹۱). یک ورودی (تصویر)، یک خروجی (فایل
فلاپی ۱٫۴۴ مگابایتی) — بدون نیاز به هیچ نصب یا وابستگی.

---

## Features / امکانات

- Input: BMP / JPG / PNG / TIF / GIF → output: 1.44 MB floppy image (`.img`)
  ready for WinImage / RawWrite / `dd`.
- Automatic width & height from the image (same as the original DOS converter:
  a 1648×512 TIF becomes a 1648-wide, 512-row pattern), adjustable for photos.
- 1-bit threshold with live preview, soft (photo) or sharp (line-art) scaling.
- Multi-disk designs are split automatically (disk 1 = bottom rows, disk 2 = top).
- Full on-disk format implemented and **verified byte-for-byte** against
  floppies written by the original DOS software (see `FORMAT.md`).
- Persian (RTL) UI; runs on any Windows 7+ (XP likely too), no runtime needed.

## قانونی / Legal note — لطفاً بخوانید

**English:** This repository contains **only our own code**. It does **not**
include, and must never include, any Karl Mayer software, firmware, data files
(copyright blocks, LAENGE/machine settings), or design/pattern images. Those
belong to the licensed Karl Mayer setup of each user. To use this program you
load a *reference floppy image from your own licensed system* once
(`قالب از فایل` button); the extracted machine settings are cached locally in
`knitter.tpl` next to the program. Use it to interoperate with your own
machines and your own designs.

**فارسی:** در این ریپو فقط کدِ خودمان است. هیچ نرم‌افزار، فایل داده یا تصویری از
کارل مایر (بلوک کپی‌رایت، LAENGE/تنظیمات ماشین، طرح‌ها) منتشر نمی‌شود و نباید
شود. برای استفاده، یک بار فلاپی مرجعِ مقالهٔ خودتان (از سیستم لایسنس‌دار خودتان)
را با دکمهٔ «قالب از فایل» می‌دهید؛ تنظیمات ماشین در `knitter.tpl` کنار برنامه
ذخیره می‌شود.

## Usage (فارسی)

1. اولین بار: **قالب از فایل…** → یک ایمیج فلاپی کارکردهٔ همان مقاله
   (خروجی Read Floppy یا ایمیج خام ۱٫۴۴ مگابایتی). تنظیمات در `knitter.tpl`
   ذخیره می‌شود و دیگر لازم نیست تکرار شود.
2. **بازکردن تصویر…** — نام طرح و تاریخ خودکار پر می‌شوند؛ عرض/ارتفاع = ابعاد
   خود تصویر (برای عکس می‌توانید تغییر دهید تا مقیاس شود).
3. آستانهٔ سیاه/سفید و نوع مقیاس (نرم برای عکس، تیز برای طرح خطی) را تنظیم کنید؛
   پیش‌نمایش همان چیزی است که بافته می‌شود (پیکسل تیره = بافته).
4. **ساخت فایل فلاپی** — فایل `.img` کنار تصویر ساخته می‌شود؛ طرح‌های بلند
   خودکار دو-دیسکی می‌شوند (`-disk2.img`).

## Build

```
x86_64-w64-mingw32-gcc -O2 -municode -mwindows -static -finput-charset=UTF-8 \
    -o knitter.exe main.c tdc_format.c -lgdiplus -lcomdlg32 -lcomctl32 -lgdi32
```

Native core tests (byte-exact against real floppy samples you supply locally):

```
gcc -O2 -o test_core test_core.c tdc_format.c
./make_vectors.py          # needs your own samples in samples/
./test_core samples/X_image testdata/X.rows <wbits> <h> <wpx>
```

## Documentation

`FORMAT.md` — complete description of the Karl Mayer TDC floppy format
(directory records, MUSTER.FAC/LAENGE.FAC, parameter block, per-row checksums,
copyright trailer, multi-disk layout), reverse-engineered and validated
byte-for-byte.

## License

MIT — see `LICENSE`.
