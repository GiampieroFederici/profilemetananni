/* motore/pmn_casuale.c - letture casuali dichiarate al kernel per i grandi file mappati in memoria (PMN 1.3).
 *
 * Kraken2 con --memory-mapping legge pezzi sparsi di una tabella piu' grande della memoria (PlusPF completo,
 * 110 GB). Senza un avviso il kernel, a ogni pezzo, legge dal disco anche le pagine vicine (lettura anticipata):
 * lavoro inutile, perche' il pezzo dopo sta altrove. Questa libreria si mette davanti a Kraken (LD_PRELOAD in
 * steps/32_kraken_bracken.sh) e, quando un file di almeno 1 GB viene mappato, dice al kernel che le letture
 * saranno sparse (madvise MADV_RANDOM): il kernel legge solo la pagina chiesta. Kraken non cambia e il suo
 * report resta identico al byte; cambia solo quanto disco si legge.
 *
 * La compila installer/installa_motore.sh in $PMN_HOME/lib/pmn_casuale.so (se manca, Kraken gira come prima):
 *   gcc -shared -fPIC -O2 -o pmn_casuale.so pmn_casuale.c
 * Solo Linux x86_64 (come il motore). Nessuna dipendenza oltre alla libreria C.
 */
#define _GNU_SOURCE
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#define UN_GB ((size_t) 1 << 30)

void *mmap(void *indirizzo, size_t lunghezza, int protezione, int opzioni, int fd, off_t inizio)
{
    void *p = (void *) syscall(SYS_mmap, indirizzo, lunghezza, protezione, opzioni, fd, inizio);
    if (p != MAP_FAILED && fd >= 0 && !(opzioni & MAP_ANONYMOUS) && lunghezza >= UN_GB)
        madvise(p, lunghezza, MADV_RANDOM);   /* un consiglio: se il kernel lo rifiuta non cambia nulla */
    return p;
}

void *mmap64(void *, size_t, int, int, int, off_t) __attribute__((alias("mmap")));
