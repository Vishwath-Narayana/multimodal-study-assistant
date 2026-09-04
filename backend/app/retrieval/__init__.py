"""Phase 2 retrieval package.

On macOS, `faiss` and `torch` (imported transitively by
`sentence-transformers`) both bundle their own copy of the OpenMP runtime
(`libomp`); loading both in one process aborts with an OpenMP duplicate-
runtime error unless `KMP_DUPLICATE_LIB_OK` is set before either is
imported. This is a known upstream issue (not specific to this project) —
setting it here, at the top of the package both are imported through,
covers every entrypoint (app, tests, scripts) without requiring every
caller to remember it.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
