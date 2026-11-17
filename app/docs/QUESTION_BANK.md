# Question bank

Default cardinality: 211 temperatures; 22,155 unordered pairs per group; 2,400 groups; 53,172,000 question IDs. ID=(source/config version, frozen group ID, lower temperature index, upper temperature index).

Bank.select streams every pair in blocks of 4,096, computes the exact Bernoulli mutual-information formula for the declared discrete posterior, excludes only already-presented IDs from reselection, and retains the stable first ID for exactly equal float64 scores (reference comparisons use 1e-13-bit tolerance). No Pareto, trade-off, root-count, grid-quota or top-K filter is used. Policy optimization's separate dominance reduction is not applied here.

Per-temperature welfare curves are cached. Every setting fingerprint invalidates the bank version. Source hashes, exact group memberships, SD boundaries, tie counts, settings and available Git commit are exported. A packaged container without .git records commit as unknown unless build provenance is supplied; source checksums remain available.

Full-bank measured result: ../validation/FULL_BANK_BENCHMARK.json. The elapsed time concerns a uniform-prior initial scan, not every possible posterior or hardware. Exact discrete-posterior ranking is distinct from exact continuous-prior integration.
