/* main.c — «طرح‌باف» — تبدیل تصویر به فلاپی دستگاه بافندگی جاکوارد Karl Mayer (TDC)
 * Build: x86_64-w64-mingw32-gcc -O2 -municode -mwindows -static -o knitter.exe main.c tdc_format.c -lgdiplus -lcomdlg32 -lcomctl32 -lgdi32
 * See FORMAT.md for the reverse-engineered format. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <gdiplus/gdiplus.h>
#include <gdiplus/gdiplusflat.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tdc_format.h"

/* ---------------- controls ---------------- */
#define IDC_BTN_TPL_FILE   101
#define IDC_BTN_TPL_FLOPPY 102
#define IDC_BTN_IMG        103
#define IDC_SLIDER         104
#define IDC_CHK_INVERT     105
#define IDC_RAD_SOFT       106
#define IDC_RAD_SHARP      107
#define IDC_ED_NAME        108
#define IDC_ED_DATE        109
#define IDC_ED_ROWS        110
#define IDC_BTN_SAVE       111
#define IDC_BTN_WRITE      112
#define IDC_PREVIEW        113
#define IDC_ST_TPL         114
#define IDC_ST_IMG         115
#define IDC_ST_THRESH      116

#define FLOPPY_SIZE TDC_DISK_SIZE

/* ---------------- app state ---------------- */
static HINSTANCE g_hInst;
static HWND g_hPreview, g_hStatus, g_hSlider;
static tdc_template g_tpl;
static int g_hasTpl;

/* source image (GDI+) */
static GpBitmap *g_bmp;
static int g_srcW, g_srcH;

/* design */
static uint8_t *g_rows;        /* packed design-domain rows, top-first */
static uint8_t *g_gray;        /* WxH preview bytes (0/255), top-first */
static int g_designW, g_designH;

static uint8_t *g_disk1, *g_disk2;
static int g_ndisks;
static int g_updating;         /* guard: we set ED_ROWS ourselves */
static WCHAR g_tplPath[MAX_PATH] = L"";
static WCHAR g_imgPath[MAX_PATH] = L"";
static WCHAR g_outBase[MAX_PATH] = L"";

/* ---------------- helpers ---------------- */
static void SetStatus(const WCHAR *fmt, ...)
{
    WCHAR buf[1024];
    va_list ap;
    va_start(ap, fmt);
    _vsnwprintf(buf, 1023, fmt, ap);
    va_end(ap);
    buf[1023] = 0;
    SetWindowTextW(g_hStatus, buf);
}

static void asciiify(const WCHAR *src, char *dst, int max)
{
    int n = 0;
    for (; *src && n < max - 1; src++) {
        WCHAR c = *src;
        if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
            (c >= 'a' && c <= 'z') || c == '.' || c == '_' || c == '-' || c == ' ')
            dst[n++] = (char)c;
    }
    dst[n] = 0;
}

static INT_PTR get_btn(HWND h, int id) { return (INT_PTR)GetDlgItem(h, id); }

static void enable_ui(HWND h, int hasTpl, int hasDesign)
{
    EnableWindow((HWND)get_btn(h, IDC_BTN_IMG), hasTpl);
    EnableWindow((HWND)get_btn(h, IDC_BTN_SAVE), hasDesign);
    EnableWindow((HWND)get_btn(h, IDC_BTN_WRITE), hasDesign);
}

/* ---------------- image → design ---------------- */
static void free_design(void)
{
    free(g_rows);  g_rows = NULL;
    free(g_gray);  g_gray = NULL;
    g_designW = g_designH = 0;
    free(g_disk1); g_disk1 = NULL;
    free(g_disk2); g_disk2 = NULL;
    g_ndisks = 0;
}

static void today_str(WCHAR *buf, int n)
{
    SYSTEMTIME st;
    GetLocalTime(&st);
    _snwprintf(buf, n, L"%02u.%02u.%02u", st.wDay, st.wMonth, st.wYear % 100);
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

/* Rebuild the 1-bit design from the current image + settings. */
static void rebuild_design(HWND h)
{
    HWND hInv = GetDlgItem(h, IDC_CHK_INVERT);
    int invert = SendMessageW(hInv, BM_GETCHECK, 0, 0) == BST_CHECKED;
    int soft = SendMessageW((HWND)get_btn(h, IDC_RAD_SOFT), BM_GETCHECK, 0, 0) == BST_CHECKED;
    int thresh = (int)SendMessageW(g_hSlider, TBM_GETPOS, 0, 0);
    WCHAR tmp[16];
    int W, H, x, y, target_rows;
    uint8_t *lum = NULL;

    if (!g_hasTpl || !g_bmp) return;

    W = g_tpl.width_bits;
    GetWindowTextW(GetDlgItem(h, IDC_ED_ROWS), tmp, 16);
    target_rows = _wtoi(tmp);
    if (target_rows < 1) target_rows = 1;
    H = clampi(target_rows, 1, tdc_rows_capacity(&g_tpl) * 2);
    if (H != target_rows) {
        _snwprintf(tmp, 16, L"%d", H);
        g_updating = 1;
        SetWindowTextW(GetDlgItem(h, IDC_ED_ROWS), tmp);
        g_updating = 0;
    }

    free_design();
    g_designW = W; g_designH = H;
    g_rows = malloc((size_t)H * (W / 8));
    g_gray = malloc((size_t)W * H);
    lum = malloc((size_t)W * H);
    if (!g_rows || !g_gray || !lum) {
        free(lum);
        free_design();
        SetStatus(L"کمبود حافظه");
        return;
    }

    /* lock source pixels */
    {
        GpRect rect = {0, 0, g_srcW, g_srcH};
        BitmapData bd;
        UINT stride;
        const uint8_t *px;
        if (GdipBitmapLockBits(g_bmp, &rect, ImageLockModeRead,
                               PixelFormat32bppARGB, &bd) != Ok) {
            free(lum);
            SetStatus(L"خطا در خواندن پیکسل‌های تصویر");
            return;
        }
        stride = (UINT)labs(bd.Stride);
        px = (const uint8_t *)bd.Scan0;

        /* box-average (soft) or nearest (sharp) downscale to W×H luminance */
        for (y = 0; y < H; y++) {
            int sy0 = (int)((int64_t)y * g_srcH / H);
            int sy1 = (int)((int64_t)(y + 1) * g_srcH / H);
            if (sy1 <= sy0) sy1 = sy0 + 1;
            if (soft) {
                for (x = 0; x < W; x++) {
                    int sx0 = (int)((int64_t)x * g_srcW / W);
                    int sx1 = (int)((int64_t)(x + 1) * g_srcW / W);
                    int sx, sy;
                    uint32_t sum = 0, cnt = 0;
                    if (sx1 <= sx0) sx1 = sx0 + 1;
                    for (sy = sy0; sy < sy1; sy++) {
                        const uint8_t *row = px + (size_t)sy * stride;
                        for (sx = sx0; sx < sx1; sx++) {
                            const uint8_t *p = row + (size_t)sx * 4;
                            /* 0.30R+0.59G+0.11B — ignore alpha (opaque) */
                            sum += (p[2] * 77 + p[1] * 151 + p[0] * 28) >> 8;
                            cnt++;
                        }
                    }
                    lum[(size_t)y * W + x] = (uint8_t)(sum / (cnt ? cnt : 1));
                }
            } else {
                int sy = (sy0 + sy1) / 2;
                const uint8_t *row = px + (size_t)sy * stride;
                for (x = 0; x < W; x++) {
                    int sx = (int)(((int64_t)x * 2 + 1) * g_srcW / (2 * W));
                    const uint8_t *p = row + (size_t)sx * 4;
                    lum[(size_t)y * W + x] =
                        (uint8_t)((p[2] * 77 + p[1] * 151 + p[0] * 28) >> 8);
                }
            }
        }
        GdipBitmapUnlockBits(g_bmp, &bd);
    }

    /* threshold → gray (preview) + packed rows (design domain; 1 = light) */
    {
        int dbytes = W / 8;
        int valid_last = ((g_tpl.width_px - 1) % 8) + 1;
        memset(g_rows, 0xFF, (size_t)H * dbytes);   /* pad bits = 1 (white) */
        for (y = 0; y < H; y++) {
            uint8_t *row = g_rows + (size_t)y * dbytes;
            for (x = 0; x < W; x++) {
                int dark = lum[(size_t)y * W + x] < thresh;
                if (invert) dark = !dark;
                g_gray[(size_t)y * W + x] = dark ? 0 : 255;
                if (!dark)
                    row[x >> 3] &= (uint8_t)~(0x80 >> (x & 7));
            }
        }
        /* real design columns end at width_px: force margin bits to white */
        if (g_tpl.width_px < W) {
            int bx = g_tpl.width_px >> 3, sh = 0x80 >> (g_tpl.width_px & 7);
            for (y = 0; y < H; y++) {
                uint8_t *row = g_rows + (size_t)y * dbytes;
                row[bx] |= sh;
                memset(row + bx + 1, 0xFF, (size_t)dbytes - bx - 1);
            }
        }
        (void)valid_last;
    }
    free(lum);
    InvalidateRect(g_hPreview, NULL, FALSE);
    enable_ui(h, 1, 1);
    {
        int nd = tdc_disk_count(&g_tpl, H);
        SetStatus(L"طرح: %d×%d — حدود %s دیسک (ظرفیت هر دیسک: %d ردیف)",
                  W, H, nd == 1 ? L"یک" : L"دو", tdc_rows_capacity(&g_tpl));
    }
}

/* ---------------- template loading ---------------- */
static void after_template(HWND h)
{
    WCHAR info[512];
    int cap = tdc_rows_capacity(&g_tpl);
    WCHAR aname[TDC_NAME_MAX];
    MultiByteToWideChar(CP_ACP, 0, g_tpl.name, -1, aname, TDC_NAME_MAX);
    _snwprintf(info, 512,
        L"قالب: %s\nمقالهٔ قالب: %s   عرض ماشین: %d پیکسل   ظرفیت: %d ردیف در هر دیسک",
        g_tplPath, aname, g_tpl.width_px, cap);
    SetWindowTextW(GetDlgItem(h, IDC_ST_TPL), info);
    enable_ui(h, 1, g_rows != NULL);
    rebuild_design(h);
}

static void load_template_file(HWND h)
{
    OPENFILENAMEW ofn;
    WCHAR file[MAX_PATH] = L"";
    static uint8_t disk[FLOPPY_SIZE];
    FILE *f;
    memset(&ofn, 0, sizeof ofn);
    ofn.lStructSize = sizeof ofn;
    ofn.hwndOwner = h;
    ofn.lpstrFilter = L"فایل فلاپی (*.img;*.ima;*.*)\0*.img;*.ima;*.*\0همهٔ فایل‌ها\0*.*\0";
    ofn.lpstrFile = file;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_FILEMUSTEXIST;
    if (!GetOpenFileNameW(&ofn)) return;
    f = _wfopen(file, L"rb");
    if (!f || fread(disk, 1, FLOPPY_SIZE, f) != FLOPPY_SIZE) {
        if (f) fclose(f);
        MessageBoxW(h, L"خواندن فایل ۱٫۴۴ مگابایتی ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    fclose(f);
    if (tdc_parse_template(disk, &g_tpl)) {
        MessageBoxW(h, L"این فایل شبیه فلاپی TDC نیست (دایرکتوری MUSTER/LAENGE پیدا نشد).",
                    L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    g_hasTpl = 1;
    wcscpy(g_tplPath, file);
    after_template(h);
}

static int floppy_read(uint8_t *buf)
{
    HANDLE d = CreateFileW(L"\\\\.\\A:", GENERIC_READ, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, 0, NULL);
    DWORD got;
    if (d == INVALID_HANDLE_VALUE) return GetLastError();
    if (!ReadFile(d, buf, FLOPPY_SIZE, &got, NULL) || got != FLOPPY_SIZE) {
        CloseHandle(d);
        return GetLastError() ? GetLastError() : -1;
    }
    CloseHandle(d);
    return 0;
}

static int floppy_write(const uint8_t *buf)
{
    HANDLE d = CreateFileW(L"\\\\.\\A:", GENERIC_WRITE, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, 0, NULL);
    DWORD put;
    if (d == INVALID_HANDLE_VALUE) return GetLastError();
    if (!WriteFile(d, buf, FLOPPY_SIZE, &put, NULL) || put != FLOPPY_SIZE) {
        CloseHandle(d);
        return GetLastError() ? GetLastError() : -1;
    }
    FlushFileBuffers(d);
    CloseHandle(d);
    return 0;
}

static void load_template_floppy(HWND h)
{
    static uint8_t disk[FLOPPY_SIZE];
    int rc = floppy_read(disk);
    if (rc) {
        MessageBoxW(h, L"خواندن فلاپی از درایو A: ناموفق بود.\n"
                       L"فلاپی ۱٫۴۴ را داخل درایو بگذارید یا فایل قالب را انتخاب کنید.",
                    L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    if (tdc_parse_template(disk, &g_tpl)) {
        MessageBoxW(h, L"این فلاپی شبیه فلاپی TDC نیست.", L"خطا",
                    MB_ICONERROR | MB_RTLREADING);
        return;
    }
    g_hasTpl = 1;
    wcscpy(g_tplPath, L"A:\\");
    after_template(h);
}

/* ---------------- image loading ---------------- */
static void load_image(HWND h)
{
    OPENFILENAMEW ofn;
    WCHAR file[MAX_PATH] = L"";
    GpBitmap *bmp = NULL;
    memset(&ofn, 0, sizeof ofn);
    ofn.lStructSize = sizeof ofn;
    ofn.hwndOwner = h;
    ofn.lpstrFilter = L"تصویر\0*.bmp;*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.gif\0همهٔ فایل‌ها\0*.*\0";
    ofn.lpstrFile = file;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_FILEMUSTEXIST;
    if (!GetOpenFileNameW(&ofn)) return;
    if (GdipCreateBitmapFromFile(file, &bmp) != Ok || !bmp) {
        MessageBoxW(h, L"باز کردن تصویر ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    if (g_bmp) GdipDisposeImage((GpImage *)g_bmp);
    g_bmp = bmp;
    GdipGetImageWidth((GpImage *)bmp, (UINT *)&g_srcW);
    GdipGetImageHeight((GpImage *)bmp, (UINT *)&g_srcH);
    wcscpy(g_imgPath, file);
    {
        WCHAR info[512], base[MAX_PATH], *dot;
        WCHAR rows[16];
        const WCHAR *fn = wcsrchr(file, L'\\');
        fn = fn ? fn + 1 : file;
        wcscpy(base, fn);
        dot = wcschr(base, L'.');
        if (dot) *dot = 0;
        _snwprintf(info, 512, L"تصویر: %s  (%d×%d)", fn, g_srcW, g_srcH);
        SetWindowTextW(GetDlgItem(h, IDC_ST_IMG), info);
        /* default name & rows */
        {
            char an[TDC_NAME_MAX];
            asciiify(base, an, TDC_NAME_MAX);
            if (!an[0]) strcpy(an, "DESIGN");
            MultiByteToWideChar(CP_ACP, 0, an, -1, base, MAX_PATH);
        }
        SetWindowTextW(GetDlgItem(h, IDC_ED_NAME), base);
        today_str(rows, 16);
        SetWindowTextW(GetDlgItem(h, IDC_ED_DATE), rows);
        _snwprintf(rows, 16, L"%d",
                   g_srcH ? (int)((int64_t)g_srcH * g_tpl.width_bits / g_srcW) : 512);
        SetWindowTextW(GetDlgItem(h, IDC_ED_ROWS), rows);
    }
    rebuild_design(h);
}

/* ---------------- disk building ---------------- */
static void default_out_base(HWND h, WCHAR *base, int n)
{
    WCHAR name[64];
    GetWindowTextW(GetDlgItem(h, IDC_ED_NAME), name, 64);
    if (g_outBase[0]) wcscpy(base, g_outBase);
    else _snwprintf(base, n, L"C:\\%s.img", name[0] ? name : L"DESIGN");
}

static int build_disks(HWND h)
{
    int rows = g_designH;
    int dbytes = g_designW / 8;
    int cap = tdc_rows_capacity(&g_tpl);
    int rc;
    const uint8_t *d2rows;
    char aname[TDC_NAME_MAX], adate[16];
    WCHAR wname[64];

    if (!g_rows) return -1;
    free(g_disk1); free(g_disk2);
    g_disk1 = malloc(FLOPPY_SIZE);
    g_disk2 = malloc(FLOPPY_SIZE);
    if (!g_disk1 || !g_disk2) return -2;

    GetWindowTextW(GetDlgItem(h, IDC_ED_NAME), wname, 64);
    asciiify(wname, aname, TDC_NAME_MAX);
    if (!aname[0]) strcpy(aname, "DESIGN");
    strcpy(g_tpl.name, aname);
    {
        WCHAR wdate[32];
        GetWindowTextW(GetDlgItem(h, IDC_ED_DATE), wdate, 32);
        asciiify(wdate, adate, sizeof adate);
        if (!adate[0]) { today_str(wdate, 32); asciiify(wdate, adate, sizeof adate); }
        strcpy(g_tpl.date, adate);
    }

    g_ndisks = tdc_disk_count(&g_tpl, rows);
    if (g_ndisks == 1) {
        rc = tdc_build_disk(&g_tpl, g_rows, rows, 1, 1, rows, 0, 0, g_disk1);
        g_disk2[0] = 0;
    } else {
        rc = tdc_build_disk(&g_tpl, g_rows + (size_t)(rows - cap) * dbytes, cap,
                            2, 1, cap,
                            cap + 1, rows - cap, g_disk1);
        if (rc) return rc;
        d2rows = g_rows;                        /* top part */
        rc = tdc_build_disk(&g_tpl, d2rows, rows - cap, 2, 2, cap,
                            cap + 1, rows - cap, g_disk2);
    }
    return rc;
}

static void save_disks(HWND h)
{
    OPENFILENAMEW ofn;
    WCHAR base[MAX_PATH];
    FILE *f;
    default_out_base(h, base, MAX_PATH);
    memset(&ofn, 0, sizeof ofn);
    ofn.lStructSize = sizeof ofn;
    ofn.hwndOwner = h;
    ofn.lpstrFilter = L"فایل فلاپی (*.img)\0*.img\0";
    ofn.lpstrFile = base;
    ofn.nMaxFile = MAX_PATH;
    ofn.lpstrDefExt = L"img";
    ofn.Flags = OFN_OVERWRITEPROMPT;
    if (!GetSaveFileNameW(&ofn)) return;
    wcscpy(g_outBase, base);

    if (build_disks(h)) {
        MessageBoxW(h, L"ساخت فایل فلاپی ناموفق بود (حافظه یا اندازهٔ طرح).",
                    L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    f = _wfopen(base, L"wb");
    if (!f || fwrite(g_disk1, 1, FLOPPY_SIZE, f) != FLOPPY_SIZE || fclose(f)) {
        MessageBoxW(h, L"نوشتن فایل ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    if (g_ndisks == 2) {
        WCHAR p2[MAX_PATH];
        WCHAR stem[MAX_PATH];
        wcscpy(stem, base);
        { WCHAR *dot = wcsrchr(stem, L'.'); if (dot) *dot = 0; }
        _snwprintf(p2, MAX_PATH, L"%s-disk2.img", stem);
        f = _wfopen(p2, L"wb");
        if (!f || fwrite(g_disk2, 1, FLOPPY_SIZE, f) != FLOPPY_SIZE || fclose(f)) {
            MessageBoxW(h, L"نوشتن دیسک ۲ ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
            return;
        }
        SetStatus(L"ذخیره شد: %s و %s", base, p2);
    } else {
        SetStatus(L"ذخیره شد: %s", base);
    }
    MessageBoxW(h, L"فایل فلاپی ساخته شد.\nبا WinImage یا نرم‌افزار مشابه روی فلاپی بنویسید\nیا دکمهٔ «نوشتن روی فلاپی» را بزنید.",
                L"انجام شد", MB_ICONINFORMATION | MB_RTLREADING);
}

static void write_floppy(HWND h)
{
    int rc;
    if (build_disks(h)) {
        MessageBoxW(h, L"ساخت دیسک ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    rc = floppy_write(g_disk1);
    if (rc) {
        MessageBoxW(h, L"نوشتن روی فلاپی A: ناموفق بود.\n"
                       L"فلاپی ۱٫۴۴ داخل درایو بگذارید و قفل نوشتنش را بردارید،\n"
                       L"یا فایل IMG را با WinImage بنویسید.",
                    L"خطا", MB_ICONERROR | MB_RTLREADING);
        return;
    }
    if (g_ndisks == 2) {
        if (MessageBoxW(h, L"طرح دو-دیسکی است.\nدیسک ۱ (ردیف‌های پایینی) نوشته شد.\nدیسک ۲ را در درایو بگذارید و OK بزنید.",
                        L"دیسک ۲", MB_OKCANCEL | MB_ICONINFORMATION | MB_RTLREADING) != IDOK)
            return;
        rc = floppy_write(g_disk2);
        if (rc) {
            MessageBoxW(h, L"نوشتن دیسک ۲ ناموفق بود.", L"خطا", MB_ICONERROR | MB_RTLREADING);
            return;
        }
        SetStatus(L"هر دو دیسک روی فلاپی نوشته شد.");
    } else {
        SetStatus(L"دیسک روی فلاپی نوشته شد.");
    }
}

/* ---------------- preview ---------------- */
static LRESULT CALLBACK preview_proc(HWND w, UINT m, WPARAM wp, LPARAM lp)
{
    if (m == WM_PAINT) {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(w, &ps);
        RECT rc;
        GetClientRect(w, &rc);
        FillRect(dc, &rc, (HBRUSH)GetStockObject(BLACK_BRUSH));
        if (g_gray && g_designW) {
            /* 8bpp top-down DIB from gray */
            struct { BITMAPINFOHEADER hdr; RGBQUAD pal[256]; } bi;
            void *bits;
            HBITMAP hbmp, hold;
            HDC mdc;
            int y;
            memset(&bi, 0, sizeof bi);
            bi.hdr.biSize = sizeof bi.hdr;
            bi.hdr.biWidth = g_designW;
            bi.hdr.biHeight = -g_designH;
            bi.hdr.biPlanes = 1;
            bi.hdr.biBitCount = 8;
            bi.hdr.biCompression = BI_RGB;
            bi.hdr.biClrUsed = 256;
            for (y = 0; y < 256; y++) {
                bi.pal[y].rgbBlue = bi.pal[y].rgbGreen =
                bi.pal[y].rgbRed = (BYTE)y;
                bi.pal[y].rgbReserved = 0;
            }
            hbmp = CreateDIBSection(dc, (BITMAPINFO *)&bi, DIB_RGB_COLORS, &bits, NULL, 0);
            if (hbmp) {
                for (y = 0; y < g_designH; y++) {
                    uint8_t *dst = (uint8_t *)bits + (size_t)y * ((g_designW + 3) & ~3);
                    memcpy(dst, g_gray + (size_t)y * g_designW, g_designW);
                }
                mdc = CreateCompatibleDC(dc);
                hold = SelectObject(mdc, hbmp);
                SetStretchBltMode(dc, COLORONCOLOR);
                {
                    int pw = rc.right - rc.left - 8, ph = rc.bottom - rc.top - 8;
                    double s = (double)pw / g_designW < (double)ph / g_designH
                             ? (double)pw / g_designW : (double)ph / g_designH;
                    int dw = (int)(g_designW * s), dh = (int)(g_designH * s);
                    if (dw < 1) dw = 1;
                    if (dh < 1) dh = 1;
                    SetStretchBltMode(dc, COLORONCOLOR);
                    StretchBlt(dc, rc.left + (rc.right-rc.left-dw)/2,
                               rc.top + (rc.bottom-rc.top-dh)/2, dw, dh,
                               mdc, 0, 0, g_designW, g_designH, SRCCOPY);
                }
                SelectObject(mdc, hold);
                DeleteDC(mdc);
                DeleteObject(hbmp);
            }
        }
        EndPaint(w, &ps);
        return 0;
    }
    return DefWindowProcW(w, m, wp, lp);
}

/* ---------------- window ---------------- */
static void create_controls(HWND h)
{
    HFONT hf = (HFONT)GetStockObject(DEFAULT_GUI_FONT);
    LOGFONTW lf;
    HFONT hfa;
    int y = 10;
    GetObjectW(hf, sizeof lf, &lf);
    lf.lfHeight = -16;
    wcscpy(lf.lfFaceName, L"Tahoma");
    hfa = CreateFontIndirectW(&lf);

    #define LB(c, txt, x, wdt) { HWND t = CreateWindowW(L"STATIC", txt, \
        WS_CHILD|WS_VISIBLE, x, y, wdt, 22, h, (HMENU)(INT_PTR)(c), g_hInst, NULL); \
        SendMessageW(t, WM_SETFONT, (WPARAM)hfa, 0); }
    #define BT(c, txt, x, wdt) { HWND t = CreateWindowW(L"BUTTON", txt, \
        WS_CHILD|WS_VISIBLE|BS_PUSHBUTTON, x, y, wdt, 30, h, (HMENU)(INT_PTR)(c), g_hInst, NULL); \
        SendMessageW(t, WM_SETFONT, (WPARAM)hfa, 0); }
    #define CK(c, txt, x, wdt) { HWND t = CreateWindowW(L"BUTTON", txt, \
        WS_CHILD|WS_VISIBLE|BS_AUTOCHECKBOX, x, y, wdt, 24, h, (HMENU)(INT_PTR)(c), g_hInst, NULL); \
        SendMessageW(t, WM_SETFONT, (WPARAM)hfa, 0); }
    #define RA(c, txt, x, wdt) { HWND t = CreateWindowW(L"BUTTON", txt, \
        WS_CHILD|WS_VISIBLE|BS_AUTORADIOBUTTON, x, y, wdt, 24, h, (HMENU)(INT_PTR)(c), g_hInst, NULL); \
        SendMessageW(t, WM_SETFONT, (WPARAM)hfa, 0); }
    #define ED(c, x, wdt) { HWND t = CreateWindowW(L"EDIT", L"", \
        WS_CHILD|WS_VISIBLE|WS_BORDER|ES_LEFT, x, y, wdt, 26, h, (HMENU)(INT_PTR)(c), g_hInst, NULL); \
        SendMessageW(t, WM_SETFONT, (WPARAM)hfa, 0); }

    /* RTL window mirrors x: larger x = further left visually */
    BT(IDC_BTN_TPL_FILE,  L"فلاپی مرجع از فایل…", 10, 195);
    BT(IDC_BTN_TPL_FLOPPY,L"خواندن قالب از فلاپی A:", 215, 215);
    y += 36;
    LB(IDC_ST_TPL, L"اول فلاپی مرجع (یک فلاپی کارکردهٔ همان مقاله) را باز کنید.", 10, 620);
    y += 34;
    BT(IDC_BTN_IMG, L"بازکردن تصویر…", 10, 160);
    y += 36;
    LB(IDC_ST_IMG, L"", 10, 620);
    y += 26;
    LB(0, L"آستانهٔ سیاه/سفید:", 10, 145);
    g_hSlider = CreateWindowW(L"msctls_trackbar32", L"",
        WS_CHILD|WS_VISIBLE|TBS_HORZ|TBS_AUTOTICKS, 160, y-6, 300, 34,
        h, (HMENU)(INT_PTR)IDC_SLIDER, g_hInst, NULL);
    SendMessageW(g_hSlider, TBM_SETRANGE, TRUE, MAKELPARAM(1, 254));
    SendMessageW(g_hSlider, TBM_SETPOS, TRUE, 128);
    LB(IDC_ST_THRESH, L"128", 470, 50);
    y += 40;
    CK(IDC_CHK_INVERT, L"پیکسل تیرهٔ تصویر = بافته‌شده (معمولی)", 10, 330);
    SendMessageW(GetDlgItem(h, IDC_CHK_INVERT), BM_SETCHECK, BST_CHECKED, 0);
    y += 30;
    RA(IDC_RAD_SOFT, L"مقیاس نرم (عکس)", 10, 165);
    RA(IDC_RAD_SHARP, L"مقیاس تیز (طرح خطی)", 185, 215);
    SendMessageW(GetDlgItem(h, IDC_RAD_SOFT), BM_SETCHECK, BST_CHECKED, 0);
    y += 34;
    LB(0, L"نام طرح:", 10, 90);   ED(IDC_ED_NAME, 105, 150);
    LB(0, L"تاریخ:", 270, 65);    ED(IDC_ED_DATE, 340, 85);
    LB(0, L"تعداد ردیف:", 440, 105); ED(IDC_ED_ROWS, 550, 80);
    y += 36;
    BT(IDC_BTN_SAVE,  L"ذخیرهٔ فایل(های) فلاپی…", 10, 225);
    BT(IDC_BTN_WRITE, L"نوشتن روی فلاپی A:", 245, 200);
    y += 42;

    g_hPreview = CreateWindowExW(WS_EX_NOINHERITLAYOUT, L"KNITPREVIEW", L"",
        WS_CHILD|WS_VISIBLE|WS_BORDER, 10, y, 600, 380,
        h, (HMENU)(INT_PTR)IDC_PREVIEW, g_hInst, NULL);

    g_hStatus = CreateWindowW(L"STATIC", L"آماده.", WS_CHILD|WS_VISIBLE,
        10, y+390, 600, 24, h, (HMENU)(INT_PTR)999, g_hInst, NULL);
    SendMessageW(g_hStatus, WM_SETFONT, (WPARAM)hfa, 0);
    enable_ui(h, 0, 0);
    EnableWindow((HWND)get_btn(h, IDC_BTN_IMG), FALSE);
    EnableWindow((HWND)get_btn(h, IDC_BTN_SAVE), FALSE);
    EnableWindow((HWND)get_btn(h, IDC_BTN_WRITE), FALSE);
}

static LRESULT CALLBACK wnd_proc(HWND h, UINT m, WPARAM wp, LPARAM lp)
{
    switch (m) {
    case WM_CREATE:
        create_controls(h);
        return 0;
    case WM_COMMAND:
        switch (LOWORD(wp)) {
        case IDC_BTN_TPL_FILE:   load_template_file(h); return 0;
        case IDC_BTN_TPL_FLOPPY: load_template_floppy(h); return 0;
        case IDC_BTN_IMG:        load_image(h); return 0;
        case IDC_BTN_SAVE:       save_disks(h); return 0;
        case IDC_BTN_WRITE:      write_floppy(h); return 0;
        case IDC_CHK_INVERT:
        case IDC_RAD_SOFT:
        case IDC_RAD_SHARP:
            if (HIWORD(wp) == BN_CLICKED) rebuild_design(h);
            return 0;
        case IDC_ED_ROWS:
            if (HIWORD(wp) == EN_CHANGE && !g_updating && g_hasTpl && g_bmp)
                rebuild_design(h);
            return 0;
        }
        break;
    case WM_HSCROLL:
        if ((HWND)lp == g_hSlider) {
            WCHAR t[16];
            _snwprintf(t, 16, L"%d", (int)SendMessageW(g_hSlider, TBM_GETPOS, 0, 0));
            SetWindowTextW(GetDlgItem(h, IDC_ST_THRESH), t);
            if (HIWORD(wp) == TB_ENDTRACK || HIWORD(wp) == TB_THUMBPOSITION)
                rebuild_design(h);
        }
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show)
{
    WNDCLASSW wc;
    MSG msg;
    HWND h;
    GdiplusStartupInput gdiInput;
    ULONG_PTR gdiToken;
    INITCOMMONCONTROLSEX icc;

    (void)prev;
    g_hInst = inst;

    /* hidden self-test: knitter.exe --selftest <orig.img> <rows.bin> <wbits> <h> <wpx>
     * exit 0 = rebuilt byte-exact */
    if (cmd && wcsncmp(cmd, L"--selftest", 10) == 0) {
        WCHAR *av[5];
        int ac = 0, rc, i, diffs, w, hh, wpx;
        WCHAR *p = cmd + 10;
        uint8_t *orig, *outb, *rows;
        FILE *f;
        tdc_template tpl;
        long want;
        while (ac < 5 && p) {
            while (*p == L' ') p++;
            if (!*p) break;
            av[ac++] = p;
            p = wcschr(p, L' ');
            if (p) *p++ = 0;
        }
        if (ac != 5) return 2;
        orig = malloc(FLOPPY_SIZE);
        outb = malloc(FLOPPY_SIZE);
        if (!orig || !outb) return 2;
        f = _wfopen(av[0], L"rb");
        if (!f || fread(orig, 1, FLOPPY_SIZE, f) != FLOPPY_SIZE) return 2;
        fclose(f);
        f = _wfopen(av[1], L"rb");
        if (!f) return 2;
        fseek(f, 0, SEEK_END); want = ftell(f); fseek(f, 0, SEEK_SET);
        rows = malloc(want);
        if (!rows || fread(rows, 1, want, f) != (size_t)want) return 2;
        fclose(f);
        if (tdc_parse_template(orig, &tpl)) return 3;
        w = _wtoi(av[2]); hh = _wtoi(av[3]); wpx = _wtoi(av[4]);
        if (tpl.width_bits != w || tpl.height != hh || tpl.width_px != wpx) return 4;
        rc = tdc_build_disk(&tpl, rows, hh, 1, 1, hh, 0, 0, outb);
        if (rc) return 5;
        diffs = 0;
        for (i = 0; i < FLOPPY_SIZE; i++)
            if (orig[i] != outb[i]) diffs++;
        return diffs == 0 ? 0 : 6;
    }

    icc.dwSize = sizeof icc;
    icc.dwICC = ICC_BAR_CLASSES;
    InitCommonControlsEx(&icc);

    gdiInput.GdiplusVersion = 1;
    gdiInput.DebugEventCallback = NULL;
    gdiInput.SuppressBackgroundThread = FALSE;
    gdiInput.SuppressExternalCodecs = FALSE;
    if (GdiplusStartup(&gdiToken, &gdiInput, NULL) != Ok) {
        MessageBoxW(NULL, L"راه‌اندازی GDI+ ناموفق بود.", L"خطا", MB_ICONERROR);
        return 1;
    }

    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = wnd_proc;
    wc.cbClsExtra = wc.cbWndExtra = 0;
    wc.hInstance = inst;
    wc.hIcon = LoadIconW(NULL, IDI_APPLICATION);
    wc.hCursor = LoadCursorW(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszMenuName = NULL;
    wc.lpszClassName = L"KNITMAIN";
    RegisterClassW(&wc);

    wc.style = 0;
    wc.lpfnWndProc = preview_proc;
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    wc.lpszClassName = L"KNITPREVIEW";
    RegisterClassW(&wc);

    h = CreateWindowExW(WS_EX_LAYOUTRTL | WS_EX_APPWINDOW, L"KNITMAIN",
        L"طرح‌باف — تصویر به فلاپی بافندگی جاکوارد (Karl Mayer TDC)",
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 680, 810,
        NULL, NULL, inst, NULL);
    ShowWindow(h, show);
    UpdateWindow(h);
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    GdiplusShutdown(gdiToken);
    return (int)msg.wParam;
}
