"""What the results page and the summary document say a session
showed, decided from the numbers in summary.py. A headline claims an
effect only when its test passes, so a later session never inherits
this one's conclusions.

Each question has one primary test, the contrast the literature
predicts: the N2 and P3 for sequence learning (Eimer et al. 1996;
Jongsma et al. 2006), beta over the motor cortex (Lum et al. 2024),
the ERN (Gehring et al. 1993) and the touch response opposite the
buzzed hand. Sequence learning has two (N2 and P3), so Holm's
correction runs across that pair. Every other comparison on the page
is exploratory and uncorrected."""
from __future__ import annotations

import re
from collections import Counter

ALPHA = 0.05

N2_TEST = "N2: random_posttest vs sequence_late"
P3_TEST = "P3: random_practice vs sequence_late"
ERN_TEST = "ERN: error vs correct"
TOUCH_TEST = "contra minus ipsi, 180-260 ms"
MU_TEST = "mu C3 after the buzz, 0.2-0.8 s"
REBOUND_TEST = "beta C3 after the press, 0.5-1.5 s"

MODE_NAMES = {"srt": "SRT", "buzz_hunt": "Buzz Hunt"}


def p_text(v) -> str:
    if v is None:
        return "n/a"
    return "< .001" if v < 0.001 else f"= {v:.3f}".replace("0.", ".", 1)


def holm(ps: list) -> list:
    """Holm-adjusted p values in the order given; None stays None."""
    idx = sorted((i for i, p in enumerate(ps) if p is not None), key=lambda i: ps[i])
    out = [None] * len(ps)
    run = 0.0
    for rank, i in enumerate(idx):
        run = max(run, min(1.0, (len(idx) - rank) * ps[i]))
        out[i] = run
    return out


def _passes(t: dict, sign: int, p=None) -> bool:
    p = t.get("p") if p is None else p
    d = t.get("diff")
    return p is not None and d is not None and p < ALPHA and d * sign > 0


def _and(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    if len(xs) < 2:
        return xs[0] if xs else ""
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def _ordinal(n: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
             6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
    return words.get(n, f"{n}th")


def _chance(p) -> str:
    if p is None:
        return ""
    if p < 0.001:
        return "less than 1 time in 1,000"
    if p < ALPHA:
        return f"about 1 time in {round(1 / p):,}"
    return f"{p * 100:.0f} percent of the time"


def _side(ch: str) -> str:
    m = re.search(r"(\d+)$", ch)
    if not m:
        return "midline"
    return "right" if int(m.group(1)) % 2 == 0 else "left"


def _item(head: str, text: str, short: str = "") -> dict:
    """A finding: its headline, the evidence in full for the results
    page, and one line of numbers for the short report."""
    return {"head": head, "text": text, "short": short or text}


def build(s: dict) -> dict:
    """Headlines with their evidence, the plain-words paragraph, the
    overview cards and the notes each page section shows."""
    who = s.get("participant") or "The participant"
    items, plain, cards, notes = [], [], [], {}
    recs = s.get("recordings", [])

    # ---- markers
    total, matched = s.get("markers_total", 0), s.get("markers_matched", 0)
    sd = max((r["residual_sd_ms"] or 0) for r in recs) if recs else None
    mx = max((r["residual_max_ms"] or 0) for r in recs) if recs else None
    sf = recs[0]["sfreq"] if recs else 512.0
    grain = 1000.0 / sf
    clean = bool(recs) and matched == total and all(r["codes_agree"] for r in recs) and mx <= grain
    if clean:
        rounding = grain / 12 ** 0.5
        why = (f", which is what rounding to a {sf:g} Hz sample gives on its own ({rounding:.2f} ms), "
               "so the serial path adds nothing measurable" if sd <= 1.25 * rounding
               else f", inside one {sf:g} Hz sample")
        drift = _and([f"{r['drift_ppm']:g}" for r in recs if r.get("drift_ppm") is not None])
        items.append(_item(
            "The marker system works end to end.",
            f"All {total:,} bytes the game wrote reached the amplifier in order, with the same codes. "
            f"Fitting the game's clock to the recording leaves {sd} ms of scatter (at most {mx} ms){why}. "
            f"The two computers' clocks drift {drift} parts per million.",
            f"{total:,} of {total:,} bytes in order with the same codes, {sd} ms timing scatter."))
        plain.append("The markers line up with the recording to within one sample, so every response "
                     "below is timed to the event that caused it.")
    else:
        items.append(_item(
            "Some markers did not line up.",
            f"{matched:,} of {total:,} bytes paired with the game's log, with scatter up to {mx} ms. "
            "Check the trigger box and the Status channel before reading the responses below."))
        plain.append("Not every marker lined up with the recording, so check the timing before "
                     "trusting the responses below.")
    cards.append({"k": "Markers", "v": f"{matched:,} / {total:,}", "state": "good" if clean else "bad",
                  "s": (f"in order, codes identical; scatter {sd} ms SD, at most {mx} ms" if clean
                        else f"scatter up to {mx} ms; check the trigger box")})

    # ---- SRT
    srt = s.get("srt")
    if srt:
        lr = srt.get("learning", {})
        rc = srt.get("recall", {})
        ci = lr.get("post_minus_block8_ci") or [None, None]
        learned = ci[0] is not None and ci[0] > 0
        seq = [r for r in srt.get("behaviour", []) if r["segment"].startswith("Sequence")]
        ant = seq[-1].get("anticipations") if seq else None
        n_items = rc.get("items") or 0
        cyc = rc.get("cyclic_correct")
        whole = bool(n_items) and cyc == n_items
        beyond = rc.get("chance_p") is not None and rc["chance_p"] < ALPHA
        if learned:
            head = f"{who} learned the sequence" + (
                ", and recalled all of it." if whole else
                ", and recalled most of it." if beyond else ", without being able to recall it.")
        else:
            head = "The reaction times show no clear sequence learning."
        recall = ""
        if rc:
            recall = (f" The lab's script scores the typed recall {rc['correct']} of {n_items} by position. "
                      f"The sequence repeats as a loop, and scored as a loop the answer gets {cyc} of {n_items}"
                      + (f", the whole sequence begun at its {_ordinal(rc['cyclic_start'])} item" if whole else "")
                      + (f"; a random answer does as well {_chance(rc.get('chance_p'))}" if rc.get("chance_p") is not None else "")
                      + ".")
        items.append(_item(head,
            f"Correct responses went from {lr['block1_ms']:.0f} ms in the first sequence block to "
            f"{lr['block8_ms']:.0f} ms in the last, then {lr['post_ms']:.0f} ms when random order returned: "
            f"{lr['post_minus_block8_ms']:.0f} ms slower than the last sequence block "
            f"(95% CI {ci[0]:.0f} to {ci[1]:.0f} ms)."
            + (f" Presses before the flash reached {ant * 100:.0f}% of the last sequence block." if ant else "")
            + recall,
            f"{lr['post_minus_block8_ms']:.0f} ms slower when random order returned (95% CI {ci[0]:.0f} to "
            f"{ci[1]:.0f} ms)" + (f"; recall {cyc} of {n_items} as a loop" if rc else "") + "."))
        notes["recall"] = (
            f"Asked to type the sequence, {who} entered {rc.get('recalled', '')}. The sequence was "
            f"{rc.get('actual', '')}. Scored position by position, as the lab's script scores it, that is "
            f"{rc.get('correct', 0)} of {n_items}. The sequence repeats as a loop, and as a loop the answer gets "
            f"{cyc} of {n_items}"
            + (f", the whole sequence begun at its {_ordinal(rc.get('cyclic_start', 1))} item" if whole else "")
            + (f"; a random answer scores that well {_chance(rc.get('chance_p'))}" if rc.get("chance_p") is not None else "")
            + ". " + ("This reads as explicit knowledge of the sequence." if whole or beyond
                      else "This does not show explicit knowledge of the sequence.")) if rc else ""
        cards.append({"k": "Sequence learning", "v": f"{lr.get('post_minus_block8_ms', 0):.0f} ms",
                      "state": "good" if learned else "",
                      "s": f"slower on random order after learning (95% CI {ci[0]:.0f} to {ci[1]:.0f} ms)"})
        plain.append(
            (f"In the SRT, {who} got faster as the order repeated and slower when it turned random"
             + (", and could type the sequence afterwards." if whole or beyond else ".")) if learned
            else "In the SRT the reaction times did not show the sequence being learned.")

        # flash ERPs: the two planned tests, Holm across the pair
        st = srt.get("stim_tests", {})
        n2, p3 = st.get(N2_TEST, {}), st.get(P3_TEST, {})
        adj = holm([n2.get("p"), p3.get("p")])
        n2_ok = _passes(n2, -1, adj[0])
        p3_ok = _passes(p3, +1, adj[1])
        rerp = srt.get("rerp", {})
        rn2 = None
        if rerp.get("n2_posttest_uV") is not None and rerp.get("n2_seq_late_uV") is not None:
            rn2 = rerp["n2_posttest_uV"] - rerp["n2_seq_late_uV"]
        if n2:
            n2_txt = (
                (f"After learning, random flashes drew a larger fronto-central N2 than learned ones "
                 f"({n2['diff']:+.1f} µV at FCz/Cz, 200-300 ms, p {p_text(n2['p'])}, corrected p {p_text(adj[0])})")
                if n2_ok else
                (f"Random flashes after learning differed from learned ones by {n2['diff']:+.1f} µV in the N2 window "
                 f"(FCz/Cz, 200-300 ms, p {p_text(n2['p'])}, corrected p {p_text(adj[0])}), within this recording's noise"))
            if rn2 is not None:
                n2_txt += (f", and the difference holds with the overlap between trials removed ({rn2:+.1f} µV)."
                           if n2_ok and rn2 < 0 else
                           f"; with the overlap between trials removed it is {rn2:+.1f} µV.")
            else:
                n2_txt += "."
        else:
            n2_txt = ""
        p3_txt = ""
        if p3:
            p3_txt = (
                f" The parietal P3 shrank as the flashes became predictable (practice minus late learning "
                f"{p3['diff']:+.1f} µV at Pz/CPz, p {p_text(p3['p'])}, corrected p {p_text(adj[1])})."
                if p3_ok else
                f" The parietal P3 changed by {p3['diff']:+.1f} µV from practice to late learning "
                f"(p {p_text(p3['p'])}, corrected p {p_text(adj[1])}), not a reliable change.")
        head = ("The brain's response to the flash changed with learning." if n2_ok and p3_ok else
                "Random flashes drew a larger N2 after learning." if n2_ok else
                "The P3 shrank as the flashes became predictable." if p3_ok else
                "The flash response did not reliably separate learned from random order.")
        short = []
        if n2:
            short.append(f"N2 {n2['diff']:+.1f} µV random against learned (corrected p {p_text(adj[0])})")
        if p3:
            short.append(f"P3 {p3['diff']:+.1f} µV practice against learned (corrected p {p_text(adj[1])})")
        items.append(_item(head, n2_txt + p3_txt, "; ".join(short) + "."))
        notes["erp"] = ("Both moved the way learning predicts." if n2_ok and p3_ok else
                        "The N2 moved the way learning predicts; the P3 change is not reliable here." if n2_ok else
                        "The P3 moved the way learning predicts; the N2 change is not reliable here." if p3_ok else
                        "Neither changed reliably in this session.")
        if n2:
            cards.append({"k": "N2 to random items", "v": f"{n2['diff']:+.1f} µV", "state": "good" if n2_ok else "",
                          "s": f"random minus learned at FCz/Cz, 200-300 ms, corrected p {p_text(adj[0])}"})
        if n2_ok or p3_ok:
            plain.append("The brain's response to each flash changed as the order was learned.")

        # display
        look = s.get("srt_look")
        keys = Counter((rc.get("actual") or "").split("-")) if rc.get("actual") else Counter()
        mix = ""
        if keys and len(set(keys.values())) > 1:
            byn = {}
            for k, n in keys.items():
                byn.setdefault(n, []).append(k)
            times = {1: "once", 2: "twice", 3: "three times", 4: "four times", 5: "five times"}
            mix = " (in this sequence " + _and([
                f"{_and(sorted(v))} come{'s' if len(v) == 1 else ''} up {times.get(n, f'{n} times')}"
                + (" each" if len(v) > 1 else "") for n, v in sorted(byn.items(), reverse=True)]) + ")"
        if look == "app":
            notes["display"] = (
                "This session used the game's own Reaction look, where each square lights at a different "
                "brightness and the squares sit about three times wider apart than in the lab's script, so part "
                f"of a visual difference between phases can come from which squares were lit{mix}. "
                "The flash timing on this monitor was not measured.")
        elif look == "lab":
            notes["display"] = ("The SRT drew the lab script's display. The flash timing on this monitor "
                                "was not measured.")
        else:
            notes["display"] = "The flash timing on this monitor was not measured."

        # motor-cortex rhythms
        bt = srt.get("band_tests", {})
        beta = bt.get("beta C3", {})
        beta_ok = _passes(beta, +1)
        bp = srt.get("block_power", [])
        seq_b = [r["beta_C3_dB"] for r in bp if r["segment"].startswith("Sequence")]
        traj = ""
        if bp and seq_b:
            traj = (f"Beta power over the left motor cortex (C3, opposite the responding hand) went from "
                    f"{bp[0]['beta_C3_dB']:.1f} dB in practice to {min(seq_b):.1f} dB at its lowest in the "
                    f"learning blocks and {bp[-1]['beta_C3_dB']:.1f} dB on the random post-test. ")
        side = []
        for label, key in (("alpha at C3", "alpha C3"), ("theta at FCz/Cz", "theta FCz/Cz")):
            t = bt.get(key)
            if not t:
                continue
            side.append(f"{label} also differed ({t['diff']:+.1f} dB, p {p_text(t['p'])})" if t["p"] < ALPHA
                        else f"{label} did not differ reliably (p {p_text(t['p'])})")
        if beta:
            items.append(_item(
                "Motor-cortex beta tracked learning." if beta_ok else
                "Motor-cortex beta did not reliably separate random from learned trials.",
                traj + f"After each flash it was {beta['diff']:+.1f} dB on random against learned trials "
                f"(p {p_text(beta['p'])})" + ("; " + "; ".join(side) if side else "") + "."
                + (" The lab's own SRT study found alpha and beta at C3 higher on the random block than on the "
                   "last sequence block (Lum et al. 2024)." if beta_ok else ""),
                f"Beta at C3 {beta['diff']:+.1f} dB on random against learned trials (p {p_text(beta['p'])})."))
            cards.append({"k": "Motor beta, C3", "v": f"{beta['diff']:+.1f} dB", "state": "good" if beta_ok else "",
                          "s": f"random against learned after the flash, p {p_text(beta['p'])}"})
            notes["rhythm"] = (f"{who} shows the same at C3, the motor area for the right hand." if beta_ok
                               else f"{who}'s beta at C3 did not separate the two reliably.")
            if beta_ok:
                plain.append("The beta rhythm over the hand's motor area was weaker on learned trials "
                             "than on random ones, as the lab's own SRT studies find.")

        # errors
        ern = srt.get("resp_tests", {}).get(ERN_TEST, {})
        rn = srt.get("resp_n", {})
        n_err, n_cor = rn.get("error", 0), rn.get("correct", 0)
        ern_ok = _passes(ern, -1)
        if ern:
            txt = (f"Wrong-finger presses ({n_err}) against correct ones ({n_cor}) at FCz/Cz, 0-100 ms after the "
                   f"force onset: {ern['diff']:+.1f} µV (p {p_text(ern['p'])}).")
            if rerp.get("ern_error_uV") is not None:
                txt += (f" With the flash's overlap regressed out, errors average {rerp['ern_error_uV']:+.1f} µV "
                        f"over the same window against {rerp['ern_correct_uV']:+.1f} µV for correct presses, "
                        f"lowest at {rerp['ern_peak_uV']:+.1f} µV {rerp['ern_peak_ms']:.0f} ms after the force onset.")
            cl = srt.get("ern_clusters", [])
            if cl:
                ps = sorted(c["p"] for c in cl)
                lo = min(c["t_ms"][0] for c in cl)
                hi = max(c["t_ms"][1] for c in cl)
                rng = (p_text(ps[0]) if len(ps) == 1 or ps[-1] < 0.001
                       else f"{p_text(ps[0])} to {p_text(ps[-1])[2:]}")
                txt += (f" Across all channels and times, a cluster test finds error and correct trials differing "
                        f"({len(cl)} cluster{'s' if len(cl) > 1 else ''}, p {rng}, between {lo:.0f} and {hi:.0f} ms), "
                        "though a cluster test does not show exactly where or when the difference lies "
                        "(Sassenhagen and Draschkow 2019).")
            items.append(_item(
                "Wrong presses carried an error signal." if ern_ok else
                "The error signal points the right way but is not yet reliable." if ern.get("diff", 0) < 0 else
                "No error signal yet.", txt,
                f"{ern['diff']:+.1f} µV wrong against correct at FCz/Cz, 0-100 ms (p {p_text(ern['p'])}, "
                f"{n_err} errors)."))
            cards.append({"k": "Error signal (ERN)", "v": f"{ern['diff']:+.1f} µV", "state": "good" if ern_ok else "",
                          "s": f"wrong minus correct at FCz/Cz, 0-100 ms after the force onset, p {p_text(ern['p'])}"})
            plain.append("A wrong press produced the brain's error signal." if ern_ok else
                         f"The brain's error signal after a wrong press shows in the average but is not yet "
                         f"reliable with {n_err} errors.")

    # ---- Buzz Hunt
    bz = s.get("buzz")
    if bz:
        bm = {m["measure"]: m for m in bz.get("measures", [])}
        tests = bz.get("tests", {})
        lat = tests.get(TOUCH_TEST, {})
        lat_ok = _passes(lat, -1)
        p3b = bm.get("P3", {})
        ratio = (p3b["mean_uV"] / p3b["sme_uV"]) if p3b.get("sme_uV") else None
        p3_clear = ratio is not None and ratio > 2
        txt = "A localisation buzz on the right hand"
        if lat:
            txt += (f" gave {bm['N1 contra']['mean_uV']:+.1f} µV over the left "
                    f"hemisphere (C3/CP3/CP5) against {bm['N1 ipsi']['mean_uV']:+.1f} µV over the right "
                    f"(180-260 ms, {int(lat['n'])} buzzes, p {p_text(lat['p'])})"
                    + (", the touch response opposite the buzzed hand" if lat_ok else
                       ", a difference within this recording's noise"))
        if p3b:
            txt += ((", then" if lat else "") + f" drew a P3 of {p3b['mean_uV']:+.1f} µV at Pz/CPz"
                    + (f", {ratio:.1f} times its measurement error" if ratio else ""))
        txt += "."
        mu, reb = tests.get(MU_TEST), tests.get(REBOUND_TEST)
        rhythm = []
        if mu:
            rhythm.append(f"mu (8-12 Hz) at C3 changed {mu['diff']:+.0f}{mu.get('unit', '%')} after the "
                          f"buzz (p {p_text(mu['p'])})")
        if reb:
            rhythm.append(f"beta at C3 changed {reb['diff']:+.0f}{reb.get('unit', '%')} 0.5 to 1.5 s after "
                          f"the answering press (p {p_text(reb['p'])})")
        if rhythm:
            txt += " Against the rest before each buzz, " + "; ".join(rhythm) + "."
        items.append(_item(
            "The buzz drew a touch response opposite the buzzed hand." if lat_ok else
            "The buzz drew a clear P3; the left-right touch response is not yet reliable." if p3_clear else
            "No clear brain response to the buzz yet.", txt,
            "; ".join(x for x in (
                f"P3 {p3b['mean_uV']:+.1f} µV" if p3b else "",
                f"left minus right {lat['diff']:+.1f} µV (p {p_text(lat['p'])})" if lat else "",
                f"mu at C3 {mu['diff']:+.0f}% (p {p_text(mu['p'])})" if mu else "") if x) + "."))
        if p3b:
            cards.append({"k": "Touch P3", "v": f"{p3b['mean_uV']:+.1f} µV", "state": "good" if p3_clear else "",
                          "s": f"Pz/CPz 400-650 ms after a localisation buzz; left-right p {p_text(lat.get('p'))}"})
        plain.append("A buzz on a finger produced a touch response on the opposite side of the head." if lat_ok else
                     "A buzz produced a clear attention response (the P3); the touch response on the opposite "
                     "side of the head needs more trials to be sure of." if p3_clear else
                     "The buzz did not yet produce a clear brain response.")
        mu_ok, reb_ok = _passes(mu or {}, -1), _passes(reb or {}, +1)
        said = []
        if mu:
            said.append("mu at C3 dropped after the buzz" if mu_ok else "the mu drop at C3 did not pass its test")
        if reb:
            said.append("beta at C3 rebounded after the press" if reb_ok
                        else "the beta rebound after the press did not pass its test")
        notes["touch"] = ("Here " + "; ".join(said) + ".") if said else ""
        notes["touch_caveat"] = (
            "Latencies are from the buzz command. The motor needs about 71-80 ms to start (bench, study laptop, "
            "not this PC) and longer to reach full strength, so the touch arrives later and smeared"
            + (f"; with {int(lat['n'])} buzzes the left-right difference does not pass its test "
               f"(p {p_text(lat['p'])})." if lat and not lat_ok else "."))

    # ---- data quality
    parts = [f"{MODE_NAMES.get(r['mode'], r['mode'])}: {', '.join(r['bads'])}" for r in recs if r.get("bads")]
    if parts:
        kinds = {re.sub(r" \(.*", "", v) for r in recs for v in (r.get("bad_reasons") or {}).values()}
        words = {"unlike its neighbours": "correlated poorly with their neighbours", "flat": "were flat",
                 "noisy above 55 Hz": "carried high-frequency noise"}
        sides = {_side(ch) for r in recs for ch in r.get("bads", [])}
        where = f", all on the {sides.pop()} side of the head" if len(sides) == 1 and "midline" not in sides else ""
        notes["quality"] = (f"Channels rebuilt from their neighbours by spherical-spline interpolation "
                            f"({'; '.join(parts)}). They {_and([words.get(k, k) for k in sorted(kinds)])}{where}, "
                            "which usually means poor electrode contact or muscle under that part of the cap. "
                            "Measures at or beside these sites lean on the channels around them.")
    else:
        notes["quality"] = "No channel needed rebuilding."
    return {"items": items, "plain": " ".join(plain), "cards": cards, "notes": notes}
