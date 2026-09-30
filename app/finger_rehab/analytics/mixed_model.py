"""A linear mixed model with one random intercept, fitted by REML.

Rayan's Data_analysis_Final.R fits lmer(RT ~ block + (1 | participant))
with lme4, reads the p values through lmerTest and the block means
through emmeans. This project carries no mixed-model package, so this
module is that one model in numpy and scipy. It maximises the same
restricted likelihood (REML) lme4 does, so the fixed effects, the two
variance components and the fixed-effect covariance are lmer's, and it
gives a contrast the Satterthwaite degrees of freedom lmerTest reports.
emmeans on an lmer fit uses Kenward-Roger degrees of freedom when
pbkrtest is installed, as it was on his machine; for this model the two
differ only in small unbalanced samples.

The model: y = X b + u[group] + e, with u ~ N(0, s2_u) for each group
and e ~ N(0, s2_e). Written for this one structure only; a random slope
needs a general package.

The notebook carries verbatim copies of fit_random_intercept and
lmm_contrast because it travels without this package, and a test pins
the copies to this file.

References: Patterson and Thompson (1971), Biometrika 58(3):545-554,
for REML; Bates, Maechler, Bolker and Walker (2015), Journal of
Statistical Software 67(1), for lme4; Satterthwaite (1946), Biometrics
Bulletin 2(6):110-114, and Kuznetsova, Brockhoff and Christensen (2017),
Journal of Statistical Software 82(13), for the degrees of freedom.
"""
from __future__ import annotations

import numpy as np


def fit_random_intercept(y, X, groups):
    """REML fit of y = X b + u[group] + e, as lmer(y ~ X + (1 | group)).

    y is the response, X the fixed-effect design with full column rank
    (cell-means coding, one dummy per block and no intercept, makes b
    the block means directly), groups one label per row.

    The fit works on the ratio theta = s2_u / s2_e. For a fixed theta
    the covariance of one group's rows is s2_e (I + theta 1 1'), whose
    inverse is closed form, so the generalised least squares pieces are
    sums over groups and nothing n by n is ever built. The residual
    variance is profiled out and the restricted log-likelihood is
    maximised over theta >= 0 on a grid, then refined. A theta of zero
    is a singular fit, where lmer reports a zero random-effect variance
    and the model is ordinary least squares.

    Returns a dict: beta, cov (the fixed-effect covariance), s2_u, s2_e,
    theta, n, p, n_groups, reml_loglik, singular, and the private
    _pieces function lmm_contrast differentiates.
    """
    from scipy.optimize import minimize_scalar

    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n, p = X.shape
    if len(y) != n or len(groups) != n:
        raise ValueError("y, X and groups need one row each")
    if int(np.linalg.matrix_rank(X)) < p:
        raise ValueError("X is rank deficient: drop the redundant columns")
    if n - p < 2:
        raise ValueError("fewer than two residual degrees of freedom")
    labels = np.asarray([str(g) for g in groups])
    _uniq, codes = np.unique(labels, return_inverse=True)
    k = int(codes.max()) + 1
    n_g = np.bincount(codes, minlength=k).astype(float)
    sum_x = np.zeros((k, p))
    np.add.at(sum_x, codes, X)
    sum_y = np.bincount(codes, weights=y, minlength=k)
    xtx = X.T @ X
    xty = X.T @ y
    yty = float(y @ y)

    def pieces(theta):
        """X'W^-1 X, b, r'W^-1 r, log|W| and log|X'W^-1 X| at theta,
        where V = s2_e W."""
        c = theta / (1.0 + theta * n_g)
        a = xtx - sum_x.T @ (c[:, None] * sum_x)
        b_rhs = xty - sum_x.T @ (c * sum_y)
        ywy = yty - float(np.sum(c * sum_y * sum_y))
        beta = np.linalg.solve(a, b_rhs)
        rwr = max(ywy - float(beta @ b_rhs), 0.0)
        logdet_w = float(np.sum(np.log1p(theta * n_g)))
        logdet_a = float(np.linalg.slogdet(a)[1])
        return a, beta, rwr, logdet_w, logdet_a

    def neg_profiled(theta):
        _a, _beta, rwr, logdet_w, logdet_a = pieces(theta)
        if rwr <= 0.0:
            return np.inf
        return 0.5 * ((n - p) * np.log(rwr / (n - p)) + logdet_w + logdet_a)

    # theta = phi / (1 - phi) maps phi in [0, 1) onto theta in [0, inf).
    phis = np.concatenate([[0.0], np.linspace(1e-6, 1.0 - 1e-9, 400)])
    values = [neg_profiled(ph / (1.0 - ph)) for ph in phis]
    best = int(np.argmin(values))
    lo = phis[max(best - 1, 0)]
    hi = phis[min(best + 1, len(phis) - 1)]
    phi = phis[best]
    if hi > lo:
        res = minimize_scalar(lambda ph: neg_profiled(ph / (1.0 - ph)),
                              bounds=(lo, hi), method="bounded",
                              options={"xatol": 1e-12})
        if res.fun <= values[best]:
            phi = float(res.x)
    theta = phi / (1.0 - phi)
    a, beta, rwr, logdet_w, logdet_a = pieces(theta)
    s2_e = rwr / (n - p)
    s2_u = theta * s2_e
    cov = s2_e * np.linalg.inv(a)
    reml_loglik = -0.5 * ((n - p) * np.log(2.0 * np.pi) + (n - p) * np.log(s2_e)
                          + logdet_w + logdet_a + (n - p))
    return {"beta": beta, "cov": cov, "s2_u": float(s2_u),
            "s2_e": float(s2_e), "theta": float(theta), "n": int(n),
            "p": int(p), "n_groups": int(k),
            "reml_loglik": float(reml_loglik),
            "singular": bool(theta < 1e-8), "_pieces": pieces}


def lmm_contrast(fit, weights, level=0.95):
    """One linear combination w'b of a fit_random_intercept fit: the
    estimate, its standard error, Satterthwaite degrees of freedom, t,
    the two-sided p and the interval at `level`.

    The degrees of freedom are 2 v^2 / (g' A g), where v is the
    variance of w'b as a function of the two variance components, g
    its gradient and A their asymptotic covariance, the inverse of the
    negative Hessian of the restricted log-likelihood (lmerTest's
    method). Both derivatives are central differences. A singular fit
    (s2_u of zero) is ordinary least squares, so its degrees of freedom
    are the residual n - p.
    """
    from scipy import stats

    w = np.asarray(weights, dtype=float)
    estimate = float(w @ fit["beta"])
    var = float(w @ fit["cov"] @ w)
    se = float(np.sqrt(var)) if var > 0 else float("nan")
    n, p = fit["n"], fit["p"]
    if fit["singular"]:
        df = float(n - p)
    else:
        pieces = fit["_pieces"]

        def v_of(s2u, s2e):
            a = pieces(s2u / s2e)[0]
            return s2e * float(w @ np.linalg.solve(a, w))

        def loglik(s2u, s2e):
            _a, _beta, rwr, logdet_w, logdet_a = pieces(s2u / s2e)
            return -0.5 * (n * np.log(s2e) + logdet_w + logdet_a
                           - p * np.log(s2e) + rwr / s2e)

        s = np.array([fit["s2_u"], fit["s2_e"]])
        h = 1e-4 * s
        grad = np.empty(2)
        for i in range(2):
            up, dn = s.copy(), s.copy()
            up[i] += h[i]
            dn[i] -= h[i]
            grad[i] = (v_of(*up) - v_of(*dn)) / (2.0 * h[i])
        hess = np.empty((2, 2))
        f0 = loglik(*s)
        for i in range(2):
            for j in range(2):
                if i == j:
                    up, dn = s.copy(), s.copy()
                    up[i] += h[i]
                    dn[i] -= h[i]
                    hess[i, i] = (loglik(*up) - 2.0 * f0
                                  + loglik(*dn)) / h[i] ** 2
                else:
                    pp, pm, mp, mm = s.copy(), s.copy(), s.copy(), s.copy()
                    pp[i] += h[i]; pp[j] += h[j]
                    pm[i] += h[i]; pm[j] -= h[j]
                    mp[i] -= h[i]; mp[j] += h[j]
                    mm[i] -= h[i]; mm[j] -= h[j]
                    hess[i, j] = (loglik(*pp) - loglik(*pm) - loglik(*mp)
                                  + loglik(*mm)) / (4.0 * h[i] * h[j])
        try:
            acov = np.linalg.inv(-hess)
            denom = float(grad @ acov @ grad)
            df = 2.0 * var ** 2 / denom if denom > 0 else float(n - p)
        except np.linalg.LinAlgError:
            df = float(n - p)
        df = float(min(max(df, 1.0), n - p))
    t_val = estimate / se if se and np.isfinite(se) and se > 0 else float("nan")
    p_val = (float(2.0 * stats.t.sf(abs(t_val), df))
             if np.isfinite(t_val) else float("nan"))
    crit = float(stats.t.ppf(0.5 + level / 2.0, df))
    return {"estimate": estimate, "SE": se, "df": df, "t": t_val,
            "p": p_val, "lower": estimate - crit * se,
            "upper": estimate + crit * se}
