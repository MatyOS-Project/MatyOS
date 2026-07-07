#include "zip.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char zip_err[256];

/* ---- CRC32 (zip polynomial) ---- */
static unsigned crc_tab[256];
static int crc_ready = 0;
static void crc_init(void) {
    for (unsigned i = 0; i < 256; i++) {
        unsigned c = i;
        for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        crc_tab[i] = c;
    }
    crc_ready = 1;
}
static unsigned crc32(const unsigned char *p, size_t n) {
    if (!crc_ready) crc_init();
    unsigned c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) c = crc_tab[(c ^ p[i]) & 0xFF] ^ (c >> 8);
    return c ^ 0xFFFFFFFFu;
}

/* ---- writer ---- */
typedef struct { char *name; unsigned crc; unsigned size; unsigned off; } WEnt;
struct Zip { FILE *f; unsigned off; WEnt *ents; int n, cap; };

static void put16(FILE *f, unsigned v) { fputc(v & 0xFF, f); fputc((v >> 8) & 0xFF, f); }
static void put32(FILE *f, unsigned v) { for (int i = 0; i < 4; i++) fputc((v >> (8*i)) & 0xFF, f); }

Zip *zip_create(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) { snprintf(zip_err, sizeof zip_err, "cannot create %s", path); return NULL; }
    Zip *z = (Zip *)malloc(sizeof(Zip));
    z->f = f; z->off = 0; z->ents = NULL; z->n = 0; z->cap = 0;
    return z;
}

int zip_add(Zip *z, const char *name, const void *data, size_t len) {
    unsigned crc = crc32((const unsigned char *)data, len);
    unsigned nlen = (unsigned)strlen(name);
    if (z->n == z->cap) { z->cap = z->cap ? z->cap * 2 : 16; z->ents = realloc(z->ents, sizeof(WEnt) * z->cap); }
    z->ents[z->n].name = strcpy((char *)malloc(nlen + 1), name);
    z->ents[z->n].crc = crc; z->ents[z->n].size = (unsigned)len; z->ents[z->n].off = z->off;
    z->n++;
    /* local file header */
    put32(z->f, 0x04034b50); put16(z->f, 20); put16(z->f, 0); put16(z->f, 0);  /* ver, flags, method=0 */
    put16(z->f, 0); put16(z->f, 0);                                            /* time, date */
    put32(z->f, crc); put32(z->f, (unsigned)len); put32(z->f, (unsigned)len);  /* crc, csize, usize */
    put16(z->f, nlen); put16(z->f, 0);                                         /* name len, extra len */
    fwrite(name, 1, nlen, z->f);
    fwrite(data, 1, len, z->f);
    z->off += 30 + nlen + (unsigned)len;
    return 0;
}

int zip_close(Zip *z) {
    unsigned cd_start = z->off;
    for (int i = 0; i < z->n; i++) {
        WEnt *e = &z->ents[i];
        unsigned nlen = (unsigned)strlen(e->name);
        put32(z->f, 0x02014b50); put16(z->f, 20); put16(z->f, 20); put16(z->f, 0); put16(z->f, 0);
        put16(z->f, 0); put16(z->f, 0);                        /* time, date */
        put32(z->f, e->crc); put32(z->f, e->size); put32(z->f, e->size);
        put16(z->f, nlen); put16(z->f, 0); put16(z->f, 0);     /* name, extra, comment len */
        put16(z->f, 0); put16(z->f, 0);                        /* disk, internal attrs */
        put32(z->f, 0); put32(z->f, e->off);                   /* external attrs, local hdr offset */
        fwrite(e->name, 1, nlen, z->f);
        z->off += 46 + nlen;
    }
    unsigned cd_size = z->off - cd_start;
    put32(z->f, 0x06054b50); put16(z->f, 0); put16(z->f, 0);
    put16(z->f, z->n); put16(z->f, z->n);
    put32(z->f, cd_size); put32(z->f, cd_start); put16(z->f, 0);
    fclose(z->f);
    for (int i = 0; i < z->n; i++) free(z->ents[i].name);
    free(z->ents); free(z);
    return 0;
}

/* ---- reader ---- */
static unsigned rd16(const unsigned char *b, size_t o) { return b[o] | (b[o+1] << 8); }
static unsigned rd32(const unsigned char *b, size_t o) { return b[o] | (b[o+1]<<8) | (b[o+2]<<16) | ((unsigned)b[o+3]<<24); }

int zip_read(Arena *ar, const char *path, ZipEntry **out) {
    FILE *f = fopen(path, "rb");
    if (!f) { snprintf(zip_err, sizeof zip_err, "cannot open %s", path); return -1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *buf = (unsigned char *)malloc((size_t)sz);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { fclose(f); free(buf); snprintf(zip_err, sizeof zip_err, "read error"); return -1; }
    fclose(f);
    /* find EOCD (scan back for signature) */
    long i = sz - 22;
    while (i >= 0 && rd32(buf, i) != 0x06054b50) i--;
    if (i < 0) { free(buf); snprintf(zip_err, sizeof zip_err, "not a zip archive"); return -1; }
    int count = (int)rd16(buf, i + 10);
    unsigned cd_off = rd32(buf, i + 16);
    ZipEntry *ents = (ZipEntry *)arena_alloc(ar, sizeof(ZipEntry) * (count ? count : 1));
    unsigned p = cd_off;
    int got = 0;
    for (int k = 0; k < count; k++) {
        if (rd32(buf, p) != 0x02014b50) { free(buf); snprintf(zip_err, sizeof zip_err, "bad central directory"); return -1; }
        unsigned method = rd16(buf, p + 10);
        unsigned csize = rd32(buf, p + 20);
        unsigned nlen = rd16(buf, p + 28), elen = rd16(buf, p + 30), clen = rd16(buf, p + 32);
        unsigned lho = rd32(buf, p + 42);
        char *name = (char *)arena_alloc(ar, nlen + 1);
        memcpy(name, buf + p + 46, nlen); name[nlen] = 0;
        /* locate data via the local header */
        unsigned lnlen = rd16(buf, lho + 26), lelen = rd16(buf, lho + 28);
        unsigned data_off = lho + 30 + lnlen + lelen;
        if (method != 0) { free(buf); snprintf(zip_err, sizeof zip_err, "unsupported compression in %s (only STORE)", name); return -1; }
        unsigned char *data = (unsigned char *)arena_alloc(ar, csize ? csize : 1);
        memcpy(data, buf + data_off, csize);
        ents[got].name = name; ents[got].data = data; ents[got].len = csize; got++;
        p += 46 + nlen + elen + clen;
    }
    free(buf);
    *out = ents;
    return got;
}
