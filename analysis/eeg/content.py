"""The fixed words on the results page: methods, limits, references and
the file list. Numbers come from summary.py and the claims from
findings.py; these lines name the choices and their sources."""
from __future__ import annotations

from . import pipeline as P

METHODS = [
    "<b>Recording.</b> BioSemi ActiveTwo with ActiView, 64 scalp channels in the 10-20 extended layout, two external electrodes, 512 Hz, saved as BDF with no hardware high-pass (DC to 104 Hz). The game ran on a separate PC and wrote one byte per event through the lab's Arduino trigger box onto the low 8 bits of the Status channel.",
    "<b>Pairing the recording with the game.</b> Status-channel rising edges (mne.find_events, mask 255) were matched in order to the game's marker log (events.tsv, rows that reached the wire, in wire order). A straight line of recording time on the game's clock gives the clock map; its residuals are the marker timing scatter.",
    f"<b>Re-reference and filters.</b> BioSemi data carry no reference (CMS/DRL), so channels were re-referenced to the average of the 64 scalp channels. Mains at {P.LINE_HZ:g} and {2*P.LINE_HZ:g} Hz were notch-filtered; ERP data were band-passed {P.HP_ERP:g}-{P.LP_ERP:g} Hz with MNE's zero-phase FIR filters. A high-pass above 0.1 Hz would distort slow ERP components (Tanner et al. 2015).",
    f"<b>Bad channels.</b> A channel was rebuilt by spherical-spline interpolation (Perrin et al. 1989) when it was flat (under {P.FLAT_UV:g} µV, 1-40 Hz), noisy above 55 Hz (a z score over {P.NOISE_Z:g} against the cap's median and median absolute deviation) or correlated under {P.NEIGHBOUR_R:g} with its four nearest neighbours.",
    f"<b>Eye artefacts.</b> Independent component analysis (Picard, extended, components explaining {P.ICA_VARIANCE*100:g} percent of variance; Ablin et al. 2018) was fitted on a {P.ICA_HP:g}-{P.ICA_LP:g} Hz copy, as high-passing before ICA improves the decomposition (Winkler et al. 2015), and the components correlating with a bipolar vertical (Fp2 to below the right eye) or horizontal (left canthus to F8) eye channel at |z| over {P.EOG_Z:g} were removed from the 0.1-40 Hz data.",
    f"<b>Epochs.</b> Flash-locked SRT epochs ran -200 to 600 ms with a -200 to 0 ms baseline; response epochs were locked to each press's force onset (the game's offline onset, events.tsv onset_offset_ms) with ERP CORE's -400 to -200 ms baseline (Kappenman et al. 2021), and the ERN is also reported against the -200 to 0 ms baseline of the first pass; Buzz Hunt epochs ran -200 to 800 ms from the buzz command. Epochs over {P.REJECT_UV:g} µV peak to peak after ICA were dropped.",
    "<b>Measures.</b> Mean amplitude in fixed windows at fixed sites chosen before looking: visual P1 80-130 ms (O1/Oz/O2), N1 140-200 ms (PO7/PO8/O1/O2), N2 200-300 ms (FCz/Cz), P3 300-450 ms (Pz/CPz), ERN 0-100 ms (FCz/Cz), Pe 200-400 ms (CPz/Pz); touch N1 180-260 ms at C3/CP3/CP5 against C4/CP4/CP6 and P3 400-650 ms at Pz/CPz. Each carries its standardised measurement error, the standard error of the single-trial values (Luck et al. 2021), and an odd/even split-half reliability of the waveform.",
    "<b>Statistics within one person.</b> Conditions were compared trial against trial: a permutation test of the difference in means (5000 shuffles) with a bootstrap 95 percent interval and Cohen's d; the left-right touch difference and the rhythm changes against each trial's own rest by sign flipping; and error against correct across all channels and times by a cluster-based permutation test (1000 permutations; Maris and Oostenveld 2007), which says the two differ somewhere but not where or when (Sassenhagen and Draschkow 2019).",
    "<b>Primary and exploratory tests.</b> Each question has the test the literature predicts: the N2 (random post-test against learned blocks 7-8) and the P3 (practice against learned) for sequence learning, beta at C3 for the motor rhythm, the ERN for errors and the left-right difference for touch. The N2 and P3 are two looks at one question, so Holm's correction runs across that pair. A headline on this page claims an effect only when its primary test passes at .05; the other rows of the tables are exploratory and uncorrected.",
    "<b>Learning and recall.</b> Learning is the slowing of correct responses when random order returns after block 8, with a bootstrap 95 percent interval of the difference in medians. The typed recall is scored by position, as the lab's script does, and as a loop at its best rotation; the chance of a random answer scoring as well at its own best rotation comes from 20,000 simulated answers.",
    "<b>Overlap correction.</b> In the SRT a flash comes about 0.7 s after the last, so responses overlap. Regression ERPs (mne.stats.linear_regression_raw; Smith and Kutas 2015) estimated every flash type and press type together.",
    "<b>Time-frequency.</b> Morlet wavelets, 4-30 Hz in 1 Hz steps, cycles half the frequency. SRT random against learned trials as single-trial dB power 0-500 ms after the flash; block power by Welch's method over each block; Buzz Hunt as percent change from 0.7-0.2 s before the buzz (and 1.2-0.8 s before the press). The Buzz Hunt tests take each trial's change from its own rest as a percent of the mean rest power (ERD/ERS percent, Pfurtscheller and Lopes da Silva 1999), linear because a trial-by-trial log ratio is biased downwards: mu (8-12 Hz) at C3 0.2-0.8 s after the buzz, and beta (13-30 Hz) at C3 0.5-1.5 s after the answering press, the post-movement rebound.",
    "<b>Presses with no marker.</b> Buzz Hunt sends no byte for a press, so each answering press was placed in the recording through the clock map at its force onset, found on the force trace with the same detector the thesis uses for reaction times (Teasdale et al. 1993).",
]

def limitations(s: dict, notes: dict) -> list[str]:
    """The limits of this session, built from its own numbers."""
    out = ["<b>One participant, one session.</b> Every test compares this person's trials; it shows the pipeline "
           "and the device can measure these effects, not that they generalise."]
    out.append(f"<b>Eye channels and reference.</b> There are no mastoid electrodes, so the average reference is used, "
               f"which is standard for 64 channels. {P.EOG_BELOW} and {P.EOG_CANTHUS} are read as the eye channels "
               "from the first session's signals, not from a lab sheet, so confirm the montage with the lab.")
    if any(r.get("bads") for r in s.get("recordings", [])):
        out.append("<b>Channels rebuilt.</b> " + notes.get("quality", ""))
    out.append("<b>Screen and buzzer delays unmeasured on this PC.</b> The flash byte leaves on the frame that draws "
               "it, but the monitor's own delay and the motor's spin-up on this PC were not timed with a light sensor "
               "or a piezo, so latencies are relative to the byte, and touch latencies include a motor delay of about "
               "71-80 ms measured on the study laptop.")
    if s.get("srt_look") == "app":
        out.append("<b>The SRT display.</b> " + notes.get("display", ""))
    out.append("<b>Learning, speed and time move together.</b> Blocks run in order, so a change across blocks can "
               "come from learning, faster responding or fatigue; the random post-test is the cleanest contrast.")
    nxt = ["time the flash and the buzz on the lab PC (light sensor and microphone or piezo on the BioSemi's "
           "spare inputs)", "record mastoids and a full eye montage"]
    if s.get("srt_look") == "app":
        nxt.append("use the script's display for the SRT (the default since 8 October 2026)")
    nxt.append("run the planned handful of participants to test effects across people")
    out.append("<b>Next:</b> " + "; ".join(nxt) + ".")
    return out


REFERENCES = [
    "Ablin P, Cardoso J-F, Gramfort A (2018). Faster independent component analysis by preconditioning with Hessian approximations. IEEE Transactions on Signal Processing 66(15):4040-4049. doi:10.1109/TSP.2018.2844203",
    "Eimer M, Goschke T, Schlaghecken F, Sturmer B (1996). Explicit and implicit learning of event sequences: evidence from event-related brain potentials. JEP: Learning, Memory, and Cognition 22(4):970-987. doi:10.1037/0278-7393.22.4.970",
    "Ferdinand NK, Mecklinger A, Kray J (2008). Error and deviance processing in implicit and explicit sequence learning. Journal of Cognitive Neuroscience 20(4):629-642. doi:10.1162/jocn.2008.20046",
    "Gehring WJ, Goss B, Coles MGH, Meyer DE, Donchin E (1993). A neural system for error detection and compensation. Psychological Science 4(6):385-390. doi:10.1111/j.1467-9280.1993.tb00586.x",
    "Gramfort A, Luessi M, Larson E, et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience 7:267. doi:10.3389/fnins.2013.00267",
    "Jongsma MLA, Eichele T, Van Rijn CM, et al. (2006). Tracking pattern learning with single-trial event-related potentials. Clinical Neurophysiology 117(9):1957-1973. doi:10.1016/j.clinph.2006.05.012",
    "Kappenman ES, Farrens JL, Zhang W, Stewart AX, Luck SJ (2021). ERP CORE: an open resource for human event-related potential research. NeuroImage 225:117465. doi:10.1016/j.neuroimage.2020.117465",
    "Kiesel A, Miller J, Jolicoeur P, Brisson B (2008). Measurement of ERP latency differences: a comparison of single-participant and jackknife-based scoring methods. Psychophysiology 45(2):250-274. doi:10.1111/j.1469-8986.2007.00618.x",
    "Luck SJ, Stewart AX, Simmons AM, Rhemtulla M (2021). Standardized measurement error: a universal metric of data quality for averaged event-related potentials. Psychophysiology 58(6):e13793. doi:10.1111/psyp.13793",
    "Lum JAG, Barham MP, Hyde C, et al. (2024). Top-down and bottom-up oscillatory dynamics regulate implicit visuomotor sequence learning. Cerebral Cortex 34(7):bhae266. doi:10.1093/cercor/bhae266",
    "Lum JAG, Clark GM, Barhoun P, et al. (2023). Neural basis of implicit motor sequence learning: modulation of cortical power. Psychophysiology 60(2):e14179. doi:10.1111/psyp.14179",
    "Lum JAG, Hamilton KM, Leow L-A, Marinovic W, et al. (2025). Atypical beta oscillatory dynamics are related to poor procedural learning in children with developmental coordination disorder. Developmental Science 28(4):e70031. doi:10.1111/desc.70031",
    "Maris E, Oostenveld R (2007). Nonparametric statistical testing of EEG- and MEG-data. Journal of Neuroscience Methods 164(1):177-190. doi:10.1016/j.jneumeth.2007.03.024",
    "Miller J, Patterson T, Ulrich R (1998). Jackknife-based method for measuring LRP onset latency differences. Psychophysiology 35(1):99-115. doi:10.1111/1469-8986.3510099",
    "Olvet DM, Hajcak G (2009). The stability of error-related brain activity with increasing trials. Psychophysiology 46(5):957-961. doi:10.1111/j.1469-8986.2009.00848.x",
    "Perrin F, Pernier J, Bertrand O, Echallier JF (1989). Spherical splines for scalp potential and current density mapping. Electroencephalography and Clinical Neurophysiology 72(2):184-187. doi:10.1016/0013-4694(89)90180-6",
    "Pfurtscheller G, Lopes da Silva FH (1999). Event-related EEG/MEG synchronization and desynchronization: basic principles. Clinical Neurophysiology 110(11):1842-1857. doi:10.1016/S1388-2457(99)00141-8",
    "Sassenhagen J, Draschkow D (2019). Cluster-based permutation tests of MEG/EEG data do not establish significance of effect latency or location. Psychophysiology 56(6):e13335. doi:10.1111/psyp.13335",
    "Smith NJ, Kutas M (2015). Regression-based estimation of ERP waveforms: II. Nonlinear effects, overlap correction, and practical considerations. Psychophysiology 52(2):169-181. doi:10.1111/psyp.12320",
    "Tanner D, Morgan-Short K, Luck SJ (2015). How inappropriate high-pass filters can produce artifactual effects and incorrect conclusions in ERP studies of language and cognition. Psychophysiology 52(8):997-1009. doi:10.1111/psyp.12437",
    "Teasdale N, Bard C, Fleury M, Young DE, Proteau L (1993). Determining movement onsets from temporal series. Journal of Motor Behavior 25(2):97-106. doi:10.1080/00222895.1993.9941644",
    "Winkler I, Debener S, Muller K-R, Tangermann M (2015). On the influence of high-pass filtering on ICA-based artifact reduction in EEG-ERP. Proceedings of IEEE EMBC 2015:4101-4105. doi:10.1109/EMBC.2015.7319296",
]

FILES = [
    ("../EEG_report.pdf", "the short report to send"),
    ("EEG_results.html", "this page: findings, figures, tables and the electrode explorer"),
    ("mne_report_srt.html, mne_report_buzz_hunt.html", "MNE's own reports: raw data, ICA, epochs and evoked responses with scalp-map sliders"),
    ("figures/", "every figure as PNG"),
    ("tables/", "behaviour, ERP measures, band power and the marker pairing as CSV"),
    ("summary.json", "every number on this page"),
]
