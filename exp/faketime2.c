/* faketime2.c — LD_PRELOAD shim: fake CLOCK_REALTIME/gettimeofday/time,
 * pass everything else (monotonic etc.) to the real libc.
 * Build: gcc -shared -fPIC -o faketime2.so faketime2.c -ldl
 * Usage: FAKE_EPOCH=<unix-seconds> LD_PRELOAD=./faketime2.so <prog>
 */
#define _GNU_SOURCE
#include <time.h>
#include <sys/time.h>
#include <stdlib.h>
#include <dlfcn.h>

static long long fake_epoch(void) {
    static long long v = -2;
    if (v == -2) {
        const char *s = getenv("FAKE_EPOCH");
        v = s ? atoll(s) : 0;
    }
    return v;
}

int clock_gettime(clockid_t clk, struct timespec *ts_ptr) {
    static int (*real)(clockid_t, void *);
    if (!real) real = dlsym(RTLD_NEXT, "clock_gettime");
    int r = real(clk, ts_ptr);
    long long fe = fake_epoch();
    if (r == 0 && fe > 0 && (clk == CLOCK_REALTIME
#ifdef CLOCK_REALTIME_COARSE
                || clk == CLOCK_REALTIME_COARSE
#endif
                )) {
        ts_ptr->tv_sec = (time_t)fe;
    }
    return r;
}

/* glibc >= 2.32 exports clock_gettime64 — redirect it too */
int clock_gettime64(clockid_t clk, struct timespec *ts_ptr) {
    return clock_gettime(clk, ts_ptr);
}

int gettimeofday(struct timeval *tv, void *tz) {
    static int (*real)(struct timeval *, void *);
    if (!real) real = dlsym(RTLD_NEXT, "gettimeofday");
    int r = real(tv, tz);
    long long fe = fake_epoch();
    if (r == 0 && fe > 0 && tv) tv->tv_sec = (time_t)fe;
    return r;
}

time_t time(time_t *t) {
    long long fe = fake_epoch();
    if (fe > 0) { if (t) *t = (time_t)fe; return (time_t)fe; }
    static time_t (*real)(time_t *);
    if (!real) real = dlsym(RTLD_NEXT, "time");
    return real(t);
}
