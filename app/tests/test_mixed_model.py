"""finger_rehab/analytics/mixed_model.py: lmer(y ~ X + (1 | group)) by REML.

Rayan's Data_analysis_Final.R fits a random intercept per participant
with lme4 and reads the block means through emmeans. R is not part of
this project, so the model is fitted here in numpy and scipy, and these
tests hold it to answers that do not depend on any package:

  - On a balanced design (every participant, every block, the same
    number of trials) REML gives the ANOVA estimates of the two
    variances, the block means are the raw block means, a within-block
    contrast has exactly N - n - k + 1 degrees of freedom, and a block
    mean has the classical Satterthwaite degrees of freedom built from
    the two mean squares.
  - With no participant effect the fit is singular, as lmer reports,
    and falls back to ordinary least squares.
  - On Rayan's own trial logs the block means and their intervals
    reproduce the error bars of his plot_estimated_means.png, which the
    earlier fixed-effect stand-in could not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.analytics import force_bench as fb  # noqa: E402
from finger_rehab.analytics.mixed_model import (  # noqa: E402
    fit_random_intercept, lmm_contrast)

FIXTURES = ROOT / "tests" / "fixtures" / "rayan"


def _balanced(n=12, k=6, m=8, sd_u=40.0, sd_e=60.0, seed=7):
    rng = np.random.default_rng(seed)
    subj = np.repeat(np.arange(n), k * m)
    blk = np.tile(np.repeat(np.arange(k), m), n)
    y = (400.0 - 15.0 * blk + rng.normal(0.0, sd_u, n)[subj]
         + rng.normal(0.0, sd_e, len(subj)))
    return y, np.eye(k)[blk], subj, blk


def _anova(y, subj, blk):
    """Mean squares of the additive two-way layout (participant and
    block, replicated cells), the classical route to both variances."""
    n, k = subj.max() + 1, blk.max() + 1
    big_n = len(y)
    m = big_n // (n * k)
    gm = y.mean()
    sm = np.array([y[subj == i].mean() for i in range(n)])
    bm = np.array([y[blk == j].mean() for j in range(k)])
    ss_t = ((y - gm) ** 2).sum()
    ss_s = k * m * ((sm - gm) ** 2).sum()
    ss_b = n * m * ((bm - gm) ** 2).sum()
    df_e = big_n - n - k + 1
    ms_s = ss_s / (n - 1)
    ms_e = (ss_t - ss_s - ss_b) / df_e
    return {"n": n, "k": k, "m": m, "ms_s": ms_s, "ms_e": ms_e,
            "df_e": df_e, "block_means": bm}


class TestBalancedDesign:
    @pytest.fixture(scope="class")
    def case(self):
        y, X, subj, blk = _balanced()
        return fit_random_intercept(y, X, subj), _anova(y, subj, blk)

    def test_reml_gives_the_anova_variances(self, case):
        fit, a = case
        assert fit["s2_e"] == pytest.approx(a["ms_e"], rel=1e-6)
        want_u = (a["ms_s"] - a["ms_e"]) / (a["k"] * a["m"])
        assert fit["s2_u"] == pytest.approx(want_u, rel=1e-4)
        assert not fit["singular"]

    def test_block_means_are_the_raw_means(self, case):
        fit, a = case
        np.testing.assert_allclose(fit["beta"], a["block_means"], atol=1e-9)

    def test_a_within_block_contrast_has_the_error_df(self, case):
        fit, a = case
        c = np.zeros(a["k"])
        c[0], c[1] = 1.0, -1.0
        r = lmm_contrast(fit, c)
        assert r["df"] == pytest.approx(a["df_e"], rel=1e-4)
        assert r["SE"] == pytest.approx(
            np.sqrt(2.0 * a["ms_e"] / (a["n"] * a["m"])), rel=1e-6)

    def test_a_block_mean_has_the_classical_satterthwaite_df(self, case):
        fit, a = case
        k, m, n = a["k"], a["m"], a["n"]
        ms_s, ms_e, df_e = a["ms_s"], a["ms_e"], a["df_e"]
        combo = ms_s + (k - 1) * ms_e
        want_df = combo ** 2 / (ms_s ** 2 / (n - 1)
                                + ((k - 1) * ms_e) ** 2 / df_e)
        r = lmm_contrast(fit, np.eye(k)[0])
        assert r["df"] == pytest.approx(want_df, rel=1e-3)
        assert r["SE"] == pytest.approx(np.sqrt(combo / (k * m * n)),
                                        rel=1e-5)
        crit = r["upper"] - r["estimate"]
        from scipy import stats
        assert crit == pytest.approx(stats.t.ppf(0.975, r["df"]) * r["SE"])


class TestEdges:
    def test_no_participant_effect_is_a_singular_fit(self):
        """Every participant given exactly the same mean, so the
        between-participant mean square is zero and REML sits on the
        boundary, where lmer reports a singular fit."""
        rng = np.random.default_rng(3)
        _y, X, subj, _blk = _balanced()
        noise = rng.normal(0.0, 60.0, len(subj))
        means = np.array([noise[subj == i].mean() for i in range(subj.max() + 1)])
        y = 400.0 + noise - means[subj]
        fit = fit_random_intercept(y, X, subj)
        assert fit["singular"]
        c = np.zeros(X.shape[1])
        c[0], c[1] = 1.0, -1.0
        assert lmm_contrast(fit, c)["df"] == len(y) - X.shape[1]

    def test_a_rank_deficient_design_is_refused(self):
        _y, X, subj, _blk = _balanced()
        bad = np.hstack([X, X[:, :1]])
        with pytest.raises(ValueError):
            fit_random_intercept(_y, bad, subj)

    def test_unbalanced_data_still_fits(self):
        y, X, subj, _blk = _balanced()
        keep = np.random.default_rng(5).random(len(y)) > 0.2
        fit = fit_random_intercept(y[keep], X[keep], subj[keep])
        assert fit["s2_u"] > 0 and fit["s2_e"] > 0
        c = np.zeros(X.shape[1])
        c[0], c[1] = 1.0, -1.0
        r = lmm_contrast(fit, c)
        assert 1.0 < r["df"] <= keep.sum() - X.shape[1]


class TestRayansData:
    @pytest.fixture(scope="class")
    def model(self):
        trials = fb.load_bench_trials(sorted(FIXTURES.glob("trials_*.csv")))
        return fb.block_model(fb.block_table(trials))

    def test_his_emmeans_error_bars(self, model):
        """Read off his plot_estimated_means.png to about a millimetre
        of the figure, which is 1.5 ms: block 0 spans about 195 to 403,
        block 1 about 103 to 328 and block 4 about 33 to 257. The old
        within-participant stand-in gave intervals a few ms wide."""
        means, _pairs, _post, _trend, info = model
        assert info["n_people"] == 3
        got = means.set_index("block")
        for block, lo, hi in ((0, 195.4, 403.7), (1, 103.3, 327.7),
                              (4, 32.9, 256.8)):
            assert got.loc[block, "lower"] == pytest.approx(lo, abs=1.5)
            assert got.loc[block, "upper"] == pytest.approx(hi, abs=1.5)

    def test_the_notebook_fits_the_same_model(self, model):
        from tests.test_analysis_gaps import _load_notebook
        ns = _load_notebook("mixed_model")
        trials = fb.load_bench_trials(sorted(FIXTURES.glob("trials_*.csv")))
        analytic = fb.block_table(trials)
        mine = ns.rayan_block_model(analytic)
        np.testing.assert_allclose(mine[0]["emmean"], model[0]["emmean"],
                                   atol=1e-9)
        np.testing.assert_allclose(mine[0]["lower"], model[0]["lower"],
                                   atol=1e-6)
        np.testing.assert_allclose(mine[1]["p_holm"], model[1]["p_holm"],
                                   atol=1e-9)
