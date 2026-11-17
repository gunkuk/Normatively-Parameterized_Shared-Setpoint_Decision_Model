# Scientific contract

Utility: u_i(T)=clip(1-|T-d_i|/6, 0.001, 1). Atkinson equally distributed equivalent welfare is the generalized mean of order 1-epsilon, with the geometric mean at epsilon=1 and the minimum at infinity. Calculations use the entire vector. Near one, centered log-moment expansion avoids cancellation; elsewhere logsumexp avoids overflow. Unit tests compare with 60-digit mpmath reference values.

Efficiency=mean(u), equity=min(u), equality=1-Gini(u), total=sum(u). These are model outputs, not direct comfort observations or energy use.

Source adapter calls the unmodified historical input loader, including its checksum and DSF tie contract. Historical decisions retain 15–31°C. App SETTINGS defaults to 12–33°C inclusive at 0.1°C. The full source specification is preserved in ../SPEC.md; later user decisions are recorded separately in IMPLEMENTATION_DETAILS.md.

A numerical optimum is conditional on the utility mapping, source scenarios, constraints, priors and chosen target weights. It cannot establish field validity. Atkinson (1970), DOI 10.1016/0022-0531(70)90039-6, supplies the welfare framework; it does not validate this application's likelihood.
