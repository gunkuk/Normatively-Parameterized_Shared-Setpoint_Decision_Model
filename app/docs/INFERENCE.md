# Inference and switching

Common-first Bayesian inference uses q midpoint quadrature; no mass is assigned to exact endpoints by the baseline continuous prior. Likelihood P(B|e)=lapse/2+(1-lapse)*sigmoid(kappa*(W_B-W_A)); defaults kappa=30,lapse=.05 are uncalibrated conventions. Updates normalize in log space. Highest-probability quadrature cells form a credible set and retain disconnected components; boundary-tail warnings distinguish underidentification.

Deterministic sets solve W_B>=W_A or the reverse. Equal-size power sums yield an exponential polynomial in e-1. Recursive derivative roots partition monotone intervals; a dominant-term bound handles the unbounded tail. The automatic power-sum root at e=1 is not assumed to be a geometric-mean tie. Root-tolerance refinement is checked before strict switching. Floating-point cancellation and unresolved very close roots remain numerical risks, not analytic guarantees.

Case B alone switches mode: two distinct, observed, internally nonempty grid sets have empty intersection with verified separation. A disconnected set, one empty grid set, or a global contradiction without such a pair does not suffice. The switch witness is retained even if later answers make a grid inconsistent. All responses remain in the common comparison posterior and each independent grid posterior. Skips are logged but never multiplied into either posterior.

A single API worker serializes expensive jobs; database row locking protects response append and checkpoint. Restart marks unfinished acquisition INTERRUPTED; operator resume recomputes the exact scan from persisted responses. It does not resume a partial numerical block from a durable GPU checkpoint.
