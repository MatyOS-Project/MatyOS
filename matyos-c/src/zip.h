/* MatyOS-C — a minimal ZIP reader/writer (STORE method, no compression) for
 * .matyos archives.  Archives we write are plain-stored, so Python's zipfile
 * reads them fine; we can read any STORE entry (DEFLATE entries are reported
 * as unsupported). */
#ifndef MATYOS_ZIP_H
#define MATYOS_ZIP_H
#include <stddef.h>
#include "term.h"   /* Arena */

typedef struct Zip Zip;
Zip *zip_create(const char *path);                              /* NULL on error */
int  zip_add(Zip *z, const char *name, const void *data, size_t len);
int  zip_close(Zip *z);                                         /* writes central dir + EOCD */

typedef struct { char *name; unsigned char *data; size_t len; } ZipEntry;
/* Read all STORE entries into an arena-allocated array. Returns count, or -1
 * (message via zip_err). */
int  zip_read(Arena *ar, const char *path, ZipEntry **out);
extern char zip_err[256];

#endif /* MATYOS_ZIP_H */
