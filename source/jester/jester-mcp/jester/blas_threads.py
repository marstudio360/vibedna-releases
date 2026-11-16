"""
Jester BLAS guard: stops the linear algebra backend from reserving a scratch
buffer per CPU core the instant NumPy loads.

NumPy ships OpenBLAS, which allocates thread-local workspace for every logical
core as soon as the library is mapped, before a single array exists. On a
16-thread laptop that is roughly 520 MB of committed memory per process, and an
MCP server pays it again in every Claude window the user has open: six windows
cost over 3 GB for buffers that never get touched.

Jester only runs cosine similarity over short embedding vectors (potion-base-8M
is pure NumPy at inference, and the personal index compares blobs a few hundred
floats wide). Threaded BLAS buys nothing at that size: fanning the work out
costs more than the work. Measured on a Ryzen 7 5800H, numpy 2.4.4, Python
3.14.4, identical results either way:

    default               523.9 MB at import
    OPENBLAS_NUM_THREADS=2 73.6 MB
    OPENBLAS_NUM_THREADS=1 41.7 MB

Import this module before NumPy. It uses setdefault, so exporting any of these
variables yourself still wins. If you later add a genuinely heavy array
workload, raise the limit for that code path rather than deleting this file.
"""

import os

_SINGLE_THREAD_VARS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)

for _var in _SINGLE_THREAD_VARS:
    os.environ.setdefault(_var, "1")
