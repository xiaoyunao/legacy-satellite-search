# Decisions

## 2026-11-16

- Use south-only DECam gr to hold selection and bandpasses fixed. Use standard sweeps with RELEASE/BRICKID/OBJID and map actual gr exposure and source mask bits independently of detected stars. Retain CLUSTER and RESOLVED rows and count them and the forced PSF flags.
- Set the initial PARSEC model to 12 Gyr and Z=0.00010 with the tabulated Chabrier IMF integral. A uses a CMD band and exact local on/off counts for proposed peaks. B uses a regularized CMD ratio and compensated disk/annulus with local variance. Its ranking statistic is empirical.
- Lock position matching to max(2 arcmin, truth circularized half-light radius) and DM within 0.75 mag. Merge within max(0.5 arcmin, 0.75 times the greater fitted scale) in each field and method, ranked by score across all DM and scale trials. Preserve the raw-to-merged assignment.
- Compare development-set quantiles at 0.1 and 0.3 reviews per effective square degree. Reserve two spatially disjoint PS1 fields for evaluation, one in each condition layer.
- Use a circular truncated fit window and an outer background annulus for candidate C. Allow a small DM and radius refinement and condition on the observed error class and hard sample limits. This is a candidate refit.
