/* MatyOS-C — an UNTRUSTED metavariable tactic engine (mirrors tactics.py).
 * It only BUILDS a proof term; the kernel re-checks it, so a bug here can make
 * a tactic fail but never certify a false theorem. */
#ifndef MATYOS_TACTICS_H
#define MATYOS_TACTICS_H
#include "parse.h"   /* Tactic */

extern char tactic_err[256];

/* Run a tactic script against `goal` (a de Bruijn type). Returns the closed
 * proof term (still to be kernel-checked by the caller), or NULL on failure
 * (message in tactic_err). */
Term *run_tactics(Arena *ar, Term *goal, Tactic *tactics, int ntactics);

#endif /* MATYOS_TACTICS_H */
