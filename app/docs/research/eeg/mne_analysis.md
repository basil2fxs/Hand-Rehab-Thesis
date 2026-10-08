# Analysing the BioSemi lab recordings with MNE-Python: verified notes

Research pass of 8 October 2026. The analysis it checked is analysis/eeg, run on the first laboratory session the same day; the sketch in Section 13 is a reference, not that code. What changed after this pass: ERP CORE's ERN baseline and epoch, rhythm tests as percent change, and the Lum citations (2024 for alpha and beta, 2023 for theta).

## 0. How to read these notes

Every source carries an access tag:

- [FT] full text read (section named where it matters)
- [FT part] part of the full text read (pages named)
- [DOC] software documentation page read (version named)
- [CODE] library source code read on GitHub (branch named)
- [ABS] abstract or bibliographic record only
- [SEC] read through another source (named), not the original
- [PROJ] this project's own files (path named)

"(arithmetic)" marks a number computed here from a verified formula. "(my design)" marks a step that no source prescribes. All quotes from sources are paraphrased.

### Versions current on 8 October 2026 (PyPI JSON and docs headers) [DOC]

| Package | Version | Released | Notes |
|---|---|---|---|
| MNE-Python | 1.13.2 | 11 Sep 2026 | Stable docs read as "MNE 1.13.2 documentation", last updated 27 Sep 2026. 1.13.1 was yanked; 1.13.0 came out 9 Sep 2026. Needs Python 3.11 or newer. |
| mne-bids | 0.20.0 | 29 Sep 2026 | Python 3.11+, mne 1.8+ |
| mne-bids-pipeline | 1.10.1 | 20 Apr 2026 | mne 1.7+, mne-bids 0.12+ |
| mne-icalabel | 0.10.0 | 5 Oct 2026 | |
| autoreject | 0.5.1 | 23 Sep 2026 | Python 3.11+ |
| pyprep | 0.9.0 | 21 Aug 2026 | |

MNE 1.13 changes that touch this work [DOC changelog v1.13]:

- Montage names standard_1005 and standard_1020 are deprecated aliases of colin27_1005 and colin27_1020 (FutureWarning, removal in 1.14). New spherical_1005, spherical_1010, spherical_1020 and fsaverage_1005 montages. The biosemi montages are unchanged.
- EpochsTFR.apply_baseline gains mode "meanlogratio".
- Epochs gains on_outside (what to do when an event's epoch runs past the data).
- set_eeg_reference with "average" now references each channel type separately by default (joint=True restores the old behaviour). No effect on EEG-only data.
- Faster EDF and BDF reading; minimum Python 3.11.

The lab PC's PsychoPy can be Python 3.10 (EEG_Lab notes) [PROJ app/docs/eeg_lab_setup.txt], so the analysis needs its own environment (Python 3.11+).

## 1. What the project already holds on this question

- app/docs/eeg_lab_setup.txt [PROJ]: the hardware chain, the code map (version 1.7), the offsets, a two-line MNE hint (read_raw_bdf with stim_channel="auto", then find_events with mask=255 and mask_type="and"), the instruction to align events.tsv by inter-marker intervals, and the validation rule (Status intervals must match t_wire intervals within one sample plus 1 ms).
- app/finger_rehab/hardware/eeg_trigger.py, functions response_offsets() and _sidecar() [PROJ]: the definitions of every events.tsv column (Section 4).
- app/docs/research/eeg/erp.md, preparation_attention.md, response_timing.md, trigger_hardware.md [PROJ]: component literature (ERN, Pe, FRN, CNV, LRP, ERD), trial counts, marker timing.
- app/docs/research/deep/srt.md [PROJ]: SRT timing (the nominal 500 ms interval is about 530 to 550 ms from key to flash and about 560 ms from a pad press, at 60 Hz; the cyclical and random groups use 250, 500 and 750 ms) and the three Lum papers.
- Missing before this pass: any MNE code; an alignment script; filter, reference and ICA choices per analysis; a plan for overlapping responses; the lab's saved sampling rate, channel count, cap labels and EXG wiring; the trigger box's fixed delay and the screen and tone delays (all still unmeasured).

## 2. Loading the BDF

### Verified facts

- read_raw_bdf (MNE 1.13.2) [DOC]: parameters input_fname, eog, misc, stim_channel="auto" (channels named "status" or "trigger", any case, become STIM), exclude (list, or a string read as a regular expression; skips channels at read time), infer_types=False (True reads "EEG Fp1"-style prefixes as types; False types every channel EEG), include, preload, units, encoding, exclude_after_unique.
- BDF layout [DOC BioSemi file_format FAQ]: 24-bit samples stored in 3 bytes; the last channel is always the Status channel, stored as trigger low byte, trigger high byte, status byte; the example header gives 31.25 nV per bit.
- How MNE reads the Status channel [CODE maint/1.13, mne/io/edf/edf.py]: BDF samples are sign-extended from bit 23. For BDF the stim channel gets calibration 1, offset 0, units 1 (no scaling). Every stim channel is then ANDed with 2**17 - 1 as it is read, so bits 0 to 16 survive (16 trigger lines plus bit 16) and bits 17 to 23 (speed mode, CMS, battery, MK2) never reach the user. The loaded values are therefore never negative.
- The read_raw_bdf docstring still shows checking the CMS bit (bit 20) from events and suggests masking with 2**16 - 1. With the 17-bit read mask, bit 20 cannot appear. Watch CMS and battery live in ActiView; do not expect them in MNE's stim channel (Section 10).
- Status bit layout [DOC BioSemi trigger_signals FAQ]: bits 0 to 15 are trigger inputs 1 to 16; bit 16 goes high when a new epoch starts; bits 17, 18, 19 and 21 are the speed mode; bit 20 is high when CMS is in range; bit 22 is high when the battery is low; bit 23 is high on an ActiveTwo MK2. Inputs have 10 kOhm pull-ups to 3.3 V, so unconnected inputs read high. Function keys F1 to F8 are ORed onto inputs 9 to 16. Inputs 1 to 8 can pause and resume saving through two reserved codes in ActiView's .cfg (PauseOff 254, PauseOn 255; -1 disables them). Trigger timing is exact to one sample; through the USB receiver, delay and jitter stay within one sample.
- Sampling and bandwidth [DOC BioSemi adjust_samplerate and adjust_filter FAQs]: ActiveTwo runs at 2, 4, 8 or 16 kHz; the -3 dB bandwidth is always one fifth of the rate (BioSemi quotes 400 Hz at 2 kHz) from a fifth-order CIC (sinc-type) decimation filter; the hardware is DC coupled with no high-pass; ActiView can downsample when it saves. ERP CORE's BioSemi data at 1024 Hz had a half-power point of 204.8 Hz [SEC Zhang et al. 2024], which fits the one-fifth rule.
- Montages [CODE maint/1.13, mne/channels/_standard_montage_utils.py and data/montages/biosemi64.txt; DOC make_standard_montage]: biosemi16, 32, 64, 128, 160 and 256 are built in. biosemi64 uses 10-20 labels (Fp1, AF7, AF3, F1 ... PO8, PO4, O2) with fiducials Nz, LPA and RPA; head_size="auto" scales to a 95 mm head. If ActiView saved A1 to B32 labels, rename them to 10-20 labels from the lab's own cap layout before set_montage. FieldTrip also warns that BioSemi caps use their own naming and that labels must match the layout [DOC FieldTrip "Getting started with BioSemi"]. The order of biosemi64.txt looks like the A1 to B32 order, but the mapping was not checked against BioSemi's Cap_coords_all.xls (not opened).
- Reference [DOC BioSemi cms&drl FAQ]: each stored signal is that electrode minus CMS; ActiView always saves these unreferenced signals; referencing is done offline; BioSemi says the offline reference adds 40 dB of common-mode rejection and that the full 80 dB is only reached once a reference is chosen. Any electrode or combination can be the reference (one electrode, the two ears, the average of all). FieldTrip says to always re-reference after reading and never to add CMS as an implicit reference channel [DOC FieldTrip].

### Memory (arithmetic)

73 channels (64 scalp, 8 EXG, Status) at 2048 Hz for 48 minutes is 430.6 million values, about 3.4 GB as float64 once preloaded. Load with preload=False, pick or drop channels, then load.

## 3. From the Status channel to an events array

### Verified facts

- find_events (MNE 1.13.2) [DOC]: find_events(raw, stim_channel=None, output="onset", consecutive="increasing", min_duration=0, shortest_event=2, mask=None, uint_cast=False, mask_type="and", initial_event=False). consecutive=True counts any change to a new non-zero value; "increasing" counts a change between non-zero codes only when the code goes up; False counts only changes from zero. min_duration is in seconds. shortest_event raises an error when two event onsets are closer than that many samples. mask_type="and" keeps the bits that are set in the mask. initial_event=True turns a non-zero first sample into an event. The docs warn that events found before decimation are not valid after it.
- Order of operations [CODE maint/1.13, mne/event.py, _find_events and _mask_trigs]: the channel is cast to int64; uint_cast (if set) casts to uint16; if anything is negative, MNE warns and takes the absolute value; steps are found on the unmasked channel, with min_duration turned into a merge window of about min_duration x sfreq samples; the mask is then applied to the step table and steps whose masked before and after values are equal are dropped; onsets are picked last, per consecutive.
- uint_cast is documented as a fix for a Neuromag STI101/STI014 problem [DOC]. MNE's BDF stim channel has no negative values (Section 2), so it is not needed here.
- mask_type defaulted to "not_and" in MNE 0.14 [DOC 0.14 find_events]. Older forum code (for example mask=2**17-256) assumed that default. Always pass mask_type.

### Recommended call (my design, built from the facts above)

```python
events_all = mne.find_events(raw, stim_channel="Status", mask=255, mask_type="and",
                             consecutive=True, min_duration=0.002, shortest_event=2)
events = events_all[np.isin(events_all[:, 2], VALID_CODES)]   # codes from markers_codes.csv
```

- mask=255: the game drives inputs 1 to 8 only. Inputs 9 to 16 may float high (pull-ups) or carry F1 to F8 presses, and bit 16 survives MNE's read mask.
- consecutive=True: if a gap between two bytes is shorter than one sample, the second byte still counts even when its code is lower.
- min_duration=0.002 (4 samples at 2048 Hz): merges one- to three-sample intermediate values if the box's eight output pins do not switch in the same instant. Real codes last 8 to 17 ms (16 to 35 samples at 2048 Hz) [PROJ eeg_lab_setup.txt]. Whether the lab's box ever shows intermediate values is unverified: plot the raw Status channel around a few bytes and look.
- Keeping only valid codes drops 255 (lines floating high before the game opens the port or after a box reset [PROJ eeg_lab_setup.txt, step 2]) and any glitch values.

## 4. Aligning Status events with events.tsv

### What events.tsv holds [PROJ app/finger_rehab/hardware/eeg_trigger.py, _sidecar and response_offsets]

- onset: seconds from the block's first raw.csv force sample, on the game's perf_counter clock. The sidecar itself says the amplifier's zero is unknown to the game.
- sample: round(onset x amplifier rate). Still the game's clock; it is not an EEG sample index.
- t_event: perf_counter time of the physical event. t_wire: perf_counter just after the byte was written (empty if it never was).
- delayed = 1: the byte waited behind another marker; t_event is still the event. failed = 1: the write failed and nothing reached the amplifier. dropped = 1: the queue shed the marker; never on the wire.
- press_offset_ms: the press sample's time on the board's own 5 ms grid minus t_wire, negative. The sidecar says the press sits at the byte's EEG sample plus this value, less the box's fixed delay. onset_offset_ms: the same for the force onset. Both are n/a for bytes other than 100 to 129 and 131, for bytes never written, and for presses not matched to a board sample (so n/a for keyboard presses, which have no board stream).
- 240 and 241 are not in the file (they fire outside any block).
- In the lab build's SRT blocks the response byte goes out at the trial's end with the press time as t_event [PROJ eeg_lab_setup.txt], so the byte's Status sample is not the press.

### What MNE offers

- No MNE function matches an external log to Status events.
- mne.preprocessing.realign_raw (1.13.2) [DOC; CODE maint/1.13, mne/preprocessing/realign.py] realigns two Raw recordings from shared event times. It needs two 1-D arrays of matched times of equal shape, fits a first-order polynomial t_raw = a + b x t_other, logs the drift as 10^6 x |1 - b| (numerically parts per million), raises an error if the Pearson correlation is not significant, and warns when fewer than 20 times are given. The same linear model is the right tool for events.
- Lab Streaming Layer's documentation [DOC LSL time synchronisation] also fits a line through clock offsets and notes that drift can be non-linear with room or computer temperature, where piecewise fits do better.

### Procedure (my design)

1. Sent list: every block's rows with t_wire present, failed = 0 and dropped = 0, sorted by t_wire. Received list: Status events with valid codes. Remove 240 and 241 from the received list (or add them from raw.csv). Expect orphan 23 and 24 bytes from restarted Force Pilot runs and 219 for abandoned blocks [PROJ eeg_lab_setup.txt].
2. Anchor each block on its 200+mode byte and its 220+mode (or 219) byte.
3. Within a block, align the two code sequences. Python's difflib.SequenceMatcher works, but only with autojunk=False: in a local test on 800 alternating stimulus and response codes with one byte removed, the default matched 200 of 799 events and autojunk=False matched all 799 (tested here with Python 3.14.3).
4. Check each matched pair by intervals: |difference of EEG times - difference of t_wire| must stay within one sample plus 1 ms (the project's own validation rule [PROJ]). Flag sent rows with no partner (lost bytes) and received events with no partner (extra bytes).
5. Fit t_EEG(byte) = a + b x t_wire by least squares over the session; report n matched, n lost, residual SD and maximum, and drift in ppm. Refit per block if the residuals curve or step. A step could mean ActiView's save was paused: a 2005 EEGLAB-list post (Cortech Solutions, not BioSemi) says the top Status byte carries pause and resume events and that ignoring it treats the data across a pause as continuous [SEC, unverified with BioSemi]. MNE's read mask removes that byte.
6. Never place EEG events for bytes that never arrived; leave those trials out of EEG analyses (behaviour can stay).

Illustration (arithmetic, assumed rate): two clocks 50 ppm apart drift 144 ms over a 48-minute session, about 295 samples at 2048 Hz. A session-wide line removes a steady rate; per-block lines absorb slow changes.

### From byte sample to event sample

- Stimulus events: the Status sample of the byte, then add the stimulus delay (eeg.marker_offsets_ms: visual 20 ms, tone 12 ms, buzz 45 ms; datasheet estimates until the photodiode and microphone run [PROJ]). A photodiode on an amplifier input measures this delay against the Status byte directly in EEG samples, box delay included.
- Press-locked events: Status sample + round(sfreq x (press_offset_ms - box_delay_ms) / 1000).
- Onset-locked events (ERN, ERD, LRP): the same with onset_offset_ms. The project's pilot found the 30 percent press point a median 50 ms after the onset, so motor potentials lock to the onset and the press lock is the check [PROJ eeg_lab_setup.txt].
- Keyboard presses (offsets n/a): use (t_event - t_wire) in place of the offset; it carries the keyboard and frame-loop latency.
- Delayed rows: the offsets are measured from t_wire, so they already absorb the wait.
- The box's fixed delay shifts every byte equally, so interval matching cannot see it; it biases only the press and onset locks. It needs a loopback or photodiode measure. For scale (arithmetic): one byte at 9600 baud with one start and one stop bit takes 1.04 ms on the wire, before any USB latency.
- In MNE: edit events[:, 0] directly for per-row shifts. mne.event.shift_time_events(events, ids, tshift, sfreq) shifts all events with the given ids by one constant [DOC]. Keep shifted copies under new codes (for example 1000 + code for press-locked, 2000 + code for onset-locked) so one array holds every lock. If two events land on one sample, Epochs(event_repeated="drop" or "merge") handles it (default "error") [DOC Epochs]. Rounding to a sample costs at most 0.24 ms at 2048 Hz (arithmetic).
- Attach trial data as Epochs metadata (block type, sequence or random, lane, hand, RT, accuracy). mne.epochs.make_metadata(events, event_id, tmin, tmax, sfreq, row_events, keep_first, keep_last) builds one row per time-locking event and can pull the first response after each stimulus [DOC].

### Can mne-bids read our events.tsv directly?

No, not as written.

- BIDS [DOC BIDS specification, events page]: onset is seconds from the first data point stored in the matching data file; negative onsets are allowed; extra columns are allowed and should be described in a JSON sidecar; every events.tsv needs a matching data file.
- read_raw_bids [CODE mne-bids main, mne_bids/read.py; DOC 0.20.0]: builds raw.annotations from onset exactly as written (no shift), takes descriptions from trial_type (falling back to value), turns n/a durations into 0, drops rows with an n/a onset, keeps extra columns as annotation extras, and ignores the sample column for annotations. When one trial_type has several values it names them trial_type/value.
- Our onset is per block and on the game's clock, and one BDF holds the whole session, so every event would land in the wrong place.
- Route: after alignment, write one session-level events table on the EEG clock with write_raw_bids(raw, bids_path, events=..., event_id=..., event_metadata=DataFrame, extra_columns_descriptions=dict) [DOC mne-bids 0.20.0]. Annotations in raw are always written too (raw.set_annotations(None) first to avoid that). raw must not be preloaded unless allow_preload=True with a format other than "auto"; format="auto" keeps the original file format when BIDS allows it. Keep the game's files beside the dataset as source data. mne-bids-pipeline then reads the aligned events.

## 5. Preprocessing

### 5.1 Order

COBIDAS MEEG (Fig. 2) gives a typical order and asks that any change be justified and reported [FT part, Pernet et al. 2020]. Proposed order (my design; each step sourced below):

1. Load, set channel types, rename labels, set the montage.
2. Provisional reference, mark bad channels.
3. Annotate breaks and pauses.
4. ICA on a filtered copy.
5. Filter the analysis copy for the analysis at hand.
6. Apply ICA, then set the final reference.
7. Epoch with metadata and per-event offsets.
8. Reject or repair epochs.
9. Measure.

### 5.2 Filters

MNE's defaults [DOC create_filter; DOC background filtering tutorial]:

- FIR is the default. With l_trans_bandwidth="auto" the transition is min(max(0.25 x l_freq, 2), l_freq); with h_trans_bandwidth="auto" it is min(max(0.25 x h_freq, 2), sfreq/2 - h_freq). With phase="zero" and the firwin design, the -6 dB point sits in the middle of the transition band. filter_length="auto" is 3.3 divided by the narrowest transition (Hamming window, firwin).
- IIR runs forward and backward (filtfilt), defaulting to a fourth-order Butterworth; the cutoff is the given frequency.
- Consequences (arithmetic): l_freq=0.1 gives a 0.1 Hz transition, a -6 dB point near 0.05 Hz and a 33 s filter (about 67,600 taps at 2048 Hz). l_freq=0.01 would need a 330 s FIR, so use IIR or no high-pass for the CNV. h_freq=30 puts -6 dB near 33.75 Hz.
- Zhang et al. (2024) give half-amplitude cutoffs of non-causal Butterworth filters at 12 dB/octave [FT], so MNE's FIR l_freq values are not the same numbers. To copy their settings, use method="iir" and check the response with mne.viz.plot_filter.

High-pass for ERPs (sources disagree; Section 10):

- The MNE tutorial summarises Acunzo et al. (2012), Widmann et al. (2015) and Tanner et al. (2015) as advising 0.1 Hz or lower, and adds that the right value depends on the signal and noise [DOC]. Tanner et al. (2015) found artefactual opposite-polarity effects from cutoffs of 0.3 Hz and above [ABS].
- Zhang, Garrett and Luck (2024), from ERP CORE data [FT, Table 1]: P3b high-pass 0.2 Hz with low-pass at least 10 Hz or none for mean amplitude; ERN 0.4 Hz with low-pass at least 20 Hz or none (10 Hz for latency measures); LRP 0.3 Hz with low-pass at least 30 Hz or none. They warn the settings may not transfer to very different paradigms or populations and that 0.1 Hz gave nearly the same SNR for P3.
- Kóbor et al. (2019), a sequence-learning ERP study, used 0.5 to 30 Hz with a 50 Hz notch [FT].
- mne-bids-pipeline docs: l_freq defaults to None and h_freq to 40; they suggest a 40 Hz low-pass and "possibly" a 1 Hz high-pass for evoked responses while warning that high-pass filtering can distort evoked waveforms [DOC 1.10.1].

Slow potentials (CNV):

- No CNV-specific filter study was found in this pass. BioSemi is DC coupled [DOC], so the CNV can be kept with no high-pass at all.
- A first-order high-pass leaves exp(-t/tau) of a sustained shift, tau = 1/(2 pi f). After 2.5 s: 0.01 Hz keeps 85 percent, 0.05 Hz 46 percent, 0.1 Hz 21 percent (arithmetic; real filters differ).
- Choose no high-pass with a pre-S1 baseline, or an IIR at 0.01 to 0.05 Hz, and compare the two in the thesis.
- Do not use Epochs(detrend=1) on CNV epochs: MNE detrends before baseline correction [DOC Epochs], and a linear detrend would remove the ramp being measured (my inference).

Low-pass and line noise:

- 0.1 to 30 Hz was Luck's (2014) general ERP recommendation [SEC Zhang et al. 2024]. For TF work, do not low-pass below the top frequency of interest. COBIDAS: sample at least 2 to 2.5 times the intended low-pass [FT part].
- BioSemi says the CMS/DRL design removes 50 Hz and that notch filters are never needed [DOC adjust_filter FAQ]; it also says unreferenced display lacks the full common-mode rejection, so judge line noise only after referencing [DOC cms&drl FAQ].
- MNE's tutorial demonstrates notching the line frequency and its harmonics (and spectrum_fit) [DOC]; mne-bids-pipeline offers notch_freq and zapline_fline [DOC]; Lum et al. (2023) notched 50 Hz [FT]; Lum et al. (2024) used RELAX with no notch [FT].
- Plan: look at the PSD after referencing; notch 50, 100, 150 Hz (Australian mains is 50 Hz) only if peaks remain and an analysis band comes near them. A 30 Hz ERP low-pass and a 30 Hz beta ceiling sit well below 50 Hz (my inference).

### 5.3 Reference

- BioSemi recordings must be referenced offline (Section 2).
- ERP CORE (BioSemi) used the P9/P10 average for most components, including ERN and LRP, and the average of all scalp sites for N170 [SEC Zhang et al. 2024]. mne-bids-pipeline's ERP CORE configs match [DOC].
- Lum et al. 2023: mastoids M1/M2 offline [FT]. Lum et al. 2024: average [FT]. Lum et al. 2025: mastoid average [FT]. Kóbor et al. 2019: average [FT].
- COBIDAS: physically linked earlobe or mastoid electrodes during recording are not recommended; always report the reference [FT part]. Offline averaging of two separately recorded mastoids is not physical linking.
- ICLabel needs a common average reference [DOC mne-icalabel].
- MNE set_eeg_reference takes one channel, a list (averaged) or "average", applied directly or as a projector [DOC tutorial]. compute_current_source_density gives a reference-free surface Laplacian (spherical splines; Perrin et al. 1987, 1989; Kayser and Tenke 2015) [DOC].
- Plan (my design): average reference for ICA and ICLabel; after ICA, linked mastoids (if EXG1 and EXG2 were on the mastoids) for ERN, FRN, CNV and P3 to match ERP CORE and the lab; average reference or CSD for mu and beta at C3 and C4.
- Before any average reference, drop unconnected EXG channels (read_raw_bdf types them EEG) and mark bad channels.

### 5.4 Bad channels

- Mark them early; noisy channels corrupt SSP and ICA; interpolation uses spherical splines on sensor positions (Perrin et al. 1989) [DOC MNE "Handling bad channels"].
- pyprep NoisyChannels (0.9.0) [DOC]: EEG only; do_detrend=True removes trends below 1 Hz first; checks for NaN and flat channels (1e-15 V), deviation (z 5), high-frequency noise (z 5, only when sfreq is above 100 Hz), correlation (1 s windows, r 0.4, 1 percent of windows), SNR, RANSAC (uses positions; correlation 0.75) and PSD (z 3, 1 to 45 Hz).
- PREP itself: multi-stage referencing with noisy-channel detection [ABS Bigdely-Shamlo et al. 2015]. autoreject also provides RANSAC [DOC].

### 5.5 ICA for eye artefacts

- MNE ICA class (1.13.2) [DOC]: high-pass before fitting, typically 1 Hz; do not baseline-correct epochs used to fit; n_components=None keeps 0.999999 of the variance; reduce the rank by 1 for an average reference and by 1 for each interpolated channel; extended Infomax via method="infomax" with fit_params=dict(extended=True), or method="picard" with fit_params=dict(ortho=False, extended=True); pass rng for reproducible results.
- MNE ICA tutorial [DOC]: the solution from the 1 Hz copy can be applied to the unfiltered data; find_bads_eog can use a frontal EEG channel as an EOG stand-in (example Fpz), with the risk that frontal channels also carry brain activity; reject=dict(eeg=200e-6) keeps large artefacts out of the fit.
- Winkler et al. (2015): a 1 to 2 Hz high-pass before ICA gave the best SNR, classification and dipolarity [ABS].
- ERP CORE fitted ICA on a 0.1 Hz copy and applied the weights to the unfiltered data [SEC Zhang et al. 2024] (conflict, Section 10).
- mne-icalabel 0.10.0 [DOC]: ICLabel expects data referenced to a common average and band-passed 1 to 100 Hz, from an extended Infomax decomposition; classes are brain, muscle artifact, eye blink, heart beat, line noise, channel noise, other. Its features are a 32 x 32 scalp image, a PSD and an autocorrelation per component [DOC get_iclabel_features], so all channels in the ICA need positions. Cite Li et al. (2022) and Pion-Tonachini et al. (2019) [DOC cite page].
- mne-bids-pipeline [DOC 1.10.1]: ica_l_freq defaults to 1.0 and must be at least 1; ica_algorithm "picard" (or "picard-extended_infomax", which matches extended Infomax); with ica_use_icalabel it requires an average reference, ica_l_freq 1 and ica_h_freq 100, applies the average reference before fitting or applying ICA, and keeps ("brain", "other") at a 0.8 threshold.
- autoreject's workflow example [DOC]: 1 Hz high-pass, epoch, autoreject (local) to find bad epochs, fit ICA on the good epochs, remove components, run autoreject again. In their example autoreject alone dropped 27 of 97 epochs and the full chain 11 of 97.

### 5.6 Epoch rejection

- autoreject 0.5.1 [DOC; ABS Jas et al. 2017]: cross-validated thresholds per sensor and trial; trials with few bad sensors are interpolated and the rest rejected; defaults n_interpolate [1, 4, 32], consensus 0 to 1 in 11 steps, cv=10.
- Fixed peak-to-peak thresholds in practice: MNE ERP tutorial eeg=100e-6 [DOC]; Lum et al. 2023 plus or minus 80 microvolts [FT]; Kóbor et al. 2019 plus or minus 100 microvolts [FT]; mne-bids-pipeline's ERP CORE ERN config uses "autoreject_global" [DOC].
- Breaks: mne.preprocessing.annotate_break(raw, events=None, min_break_duration=15.0, t_start_after_previous=5.0, t_stop_before_next=5.0) returns BAD_break annotations [DOC]. Annotate game pauses (242 to 243) as BAD_pause yourself. Epochs drop any epoch overlapping an annotation whose description starts with "bad" by default [DOC Epochs].

### 5.7 Baselines

- ERP: Epochs default baseline is (None, 0) [DOC]. In the SRT the pre-flash interval holds the previous trial's response and P3 (Section 6).
- MNE's tutorial records the debate on baseline correction as a high-pass: Tanner et al. (2015, 2016) for, Maess et al. (2016) against; it concludes the choice should follow the data [DOC background filtering].
- TF modes [CODE maint/1.13, mne/baseline.py; DOC rescale]: mean, ratio, logratio, percent, zscore, zlogratio, meanlogratio. Every log mode uses log10, so dB = 10 x logratio. percent returns a fraction (x 100 for ERD percent). baseline=(None, None) uses the whole epoch.
- MNE's TF tutorial says logratio has a negative bias that can make unchanged power look like a decrease, that meanlogratio avoids it, and that the baseline should end early to avoid leakage; it cites Kinley et al. (2026, J Neurosci Methods 110826), which I could not find [DOC; SEC].
- COBIDAS: a pre-stimulus baseline of at least three cycles of the lowest frequency [FT part]. That is 750 ms at 4 Hz and 375 ms at 8 Hz (arithmetic).
- Lum et al. 2023 and 2024 used whole-epoch dB baselines because their trials had no rest periods [FT].
- Gyurkovics et al. (2021): dB conversion assumes oscillatory and 1/f power scale together; when groups differ in 1/f level it can over- or under-state interactions or create them; check 1/f and try more than one baseline [ABS].

### 5.8 Resampling and decimation

- MNE [DOC Raw.resample; filtering tutorial; find_events]: resampling Raw jitters event timing; epoch first, then decimate; low-pass at or below one third of the new rate first, because Epochs decim does not filter; if Raw must be resampled, pass events to raw.resample; stim channels are subsampled without filtering, which can lose triggers.
- So: find events at the native rate, before anything else. For ERPs, low-pass at 85 Hz or below and decimate 2048 Hz by 8 to 256 Hz (arithmetic: 256 / 3 = 85.3). linear_regression_raw recommends about 100 Hz, via its decim argument [DOC].
- Ask the lab not to downsample in ActiView when saving: an 8 ms pulse is 2 samples at 256 Hz (arithmetic), and how ActiView treats triggers when it downsamples is not described in the BioSemi pages read here.

## 6. Overlapping responses in the SRT

### Regression ERPs (rERP)

- Smith and Kutas (2015, Part II) [FT]: overlap correction expands each predictor over latencies and fits one regression to the continuous EEG. It needs variability in timing or stimuli: with a fixed interval and identical stimuli, no method can tell which event a component belongs to. In their simulations, intervals jittered between 200 and 400 ms recovered the waveform and a fixed 300 ms interval did not. Use long windows, because the model assumes zero response outside the window. Stimulus- and response-locked rERPs can be fitted together. Filter and baseline the estimated rERP waveforms (the safest choice); ICA and re-referencing give the same result before or after. For artefacts, drop only the bad data points, or the whole epoch plus every epoch that overlaps it. The method assumes the brain sums overlapping responses linearly.
- Part I (the rERP framework): Psychophysiology 52:157-168, doi:10.1111/psyp.12317 [SEC Part II reference list].
- MNE: mne.stats.linear_regression_raw(raw, events, event_id=None, tmin=-0.1, tmax=1, covariates=None, reject=None, flat=None, tstep=1.0, decim=1, picks=None, solver="cholesky") returns a dict of Evoked [DOC 1.13.2]. tmin and tmax can be dicts per event type; covariates is a DataFrame-like object, one value per event; reject is applied to tstep-long chunks of the continuous data; about 100 Hz sampling or decim is advised. MNE's example notes that with no overlap and binary predictors the result equals plain averaging [DOC example].
- Unfold (MATLAB) [FT Ehinger and Dimigen 2019]: deconvolution needs varying overlap, varying order, or both; artefactual intervals are blanked out of the time-expanded design matrix; windows should cover the whole response (their example: -1.5 to 1 s, with pre-movement time for motor events); whether to baseline-correct is still debated, and it can be done on the betas. The paper names MNE as the maintained Python option. Development now happens in Unfold.jl (Julia), reachable from Python through juliacall; its docs warn that single-subject standard errors are too small under overlap correction [DOC juliahub mirror of Unfold.jl].

### What this means for this SRT (arithmetic from [PROJ app/docs/research/deep/srt.md])

- Flashes come 0.65 to 0.9 s apart. The P3 window (300 to 600 ms) reaches the response and, near its end, the next flash.
- In the constant 500 ms timing group, the press-to-next-flash interval is about 530 to 550 ms (keys) or about 560 ms (pads). The response kernel at latency L and the next flash's kernel at L - 0.545 s therefore always co-occur. With a stimulus window that starts at -0.2 s and a response window that runs past +0.35 s, those latencies are almost perfectly collinear; only frame jitter separates them.
- Stimulus n against response n (RT varies) and stimulus n against stimulus n+1 (the interval varies with RT) remain separable.
- The cyclical and random groups (250, 500, 750 ms) break the collinearity. Errors, anticipations and misses add more variety.
- Plan (my design): run EEG SRT sessions in a jittered timing group, or end the response window before +0.3 s; model flash (sequence), flash (random) and press, with RT as a covariate if needed.
- After a 250 ms interval the next flash lands about 280 to 300 ms after the press, inside the Pe window (Section 7.3).

## 7. Measures per analysis

### 7.1 SRT stimulus-locked N2 and P3, sequence against random

- Lock: the 30 byte plus the visual delay. Prefer the rERP of Section 6.
- P3 (ERP CORE) [SEC Zhang et al. 2024, Table 2]: Pz, mean amplitude 300 to 600 ms; epoch -0.2 to 0.8 s; baseline -0.2 to 0 s. Filters: 0.2 Hz high-pass, low-pass at least 10 Hz or none for mean amplitude [FT Zhang et al. 2024].
- Sequence-learning precedent (Kóbor et al. 2019) [FT]: centro-parietal pool CP1, CPz, CP2, P1, Pz, P2; P3 280 to 380 ms and late P3 380 to 600 ms after the stimulus; stimulus baseline -200 to 0 ms; response-locked baseline 500 to 700 ms after the response (the end of a 700 ms RSI).
- N2: no verified window was collected in this pass; the project's N2 sources are abstracts [PROJ srt.md]. Choose windows and channels in advance: COBIDAS calls choosing them from the grand-average difference double dipping [FT part], and the MNE ERP tutorial says the same [DOC].
- Trials: P3 amplitude settled at about 20 target trials (Cohen and Polich 1997) [ABS].

### 7.2 SRT theta, alpha and beta

- Lab precedent:
  - Lum et al. 2023 [FT]: response-locked epochs -1 to +1 s, analysed over plus or minus 0.5 s; complex Morlet wavelets 1 to 30 Hz in 60 log steps with 2 to 15 cycles; whole-epoch dB baseline; theta 4 to 7 Hz at F3, Fz, F4, C3, Cz, C4; cluster permutation tests.
  - Lum et al. 2024 [FT]: stimulus-locked -1 to +1.65 s (extra time for wavelet edges), then trimmed; Morlet 1 to 35 Hz in 80 log steps, 2 to 15 cycles; whole-epoch dB; theta at Cz and alpha and beta (7 to 17 Hz) at C3.
  - Lum et al. 2025 [FT]: epochs plus or minus 2 s, analysed -0.5 to 0.8 s; Morlet 1 to 35 Hz in 90 linear steps, 2 to 15 cycles; dB baseline -500 to -100 ms; beta clusters centred on C3; one hand on purpose so motor beta lateralises the same way for everyone.
  - All three used TMSi amplifiers and EEGLAB-based pipelines (RELAX in 2024 and 2025), not BioSemi and MNE [FT].
- MNE: epochs.compute_tfr(method="morlet", freqs, n_cycles=..., average=False, decim=...) replaces tfr_morlet, which the 1.13 docs mark LEGACY [DOC]. Multitaper is method="multitaper" with time_bandwidth [DOC].
- Morlet resolution [DOC mne.time_frequency.morlet]: temporal SD = n_cycles / (2 pi f); wavelets extend to plus or minus 5 SD; time FWHM = n_cycles x sqrt(2 ln 2) / (pi f).
  - With n_cycles = freqs / 2 (the MNE tutorial's choice): SD 0.080 s and time FWHM 0.187 s at every frequency; each wavelet spans about plus or minus 0.40 s (arithmetic).
  - With 3 cycles at 4 Hz: SD 0.119 s, FWHM 0.281 s, span plus or minus 0.60 s (arithmetic).
  - At 0.65 to 0.9 s between flashes, one flash's theta estimate mixes in its neighbours. Compare sequence with random blocks rather than against a pre-flash baseline, as the Lum papers did.
- Band edges: report them. COBIDAS canonical bands: theta 4 to below 8, alpha 8 to below 13, beta 13 to 30 Hz [FT part]. The Lum papers used 4 to 7, 7 to 13 (or 7 to 11) and 13 to 20 (or 12 to 17) [FT].

### 7.3 ERN and Pe (wrong presses in SRT, Adaptive, Chords)

- Lock: onset_offset_ms, with press_offset_ms as the check [PROJ].
- ERN (ERP CORE) [SEC Zhang et al. 2024, Table 2]: FCz, mean amplitude 0 to 100 ms after the response; epoch -0.6 to 0.4 s; baseline -0.4 to -0.2 s; incorrect minus correct difference wave. Filters: 0.4 Hz high-pass, low-pass at least 20 Hz or none for amplitude, 10 Hz for latency [FT Zhang et al. 2024].
- mne-bids-pipeline's ERP CORE ERN config [DOC]: l_freq 0.1, h_freq None, notch 60, resample to 128 Hz, reference P9/P10, ICA, reject "autoreject_global", epochs -0.6 to 0.4 s, baseline -0.4 to -0.2 s, conditions response/correct and response/incorrect.
- Pe: centro-parietal, about 200 to 400 ms after the response [SEC PROJ erp.md, citing Overbeek et al. 2005]; extend the epoch to +0.6 s or more.
- Trials (sources disagree, Section 10): about 6 to 8 errors give a stable average (Olvet and Hajcak 2009; Pontifex et al. 2010, with older adults needing 8) [ABS]; more than 14 were needed for test-retest reliability (Larson et al. 2010) [ABS]; the number of errors a person makes tracks ERN amplitude even with trial counts held equal, and more trials raise power for group comparisons (Fischer et al. 2017) [ABS].
- SRT: in the jittered timing groups the Pe window can contain the next flash (Section 6). Drop those trials or model them.

### 7.4 FRN (140 hit, 141 miss)

- Lock: the 140 or 141 byte, written with the outcome flash, plus the visual delay [PROJ].
- Fronto-central negativity about 250 ms after feedback (Miltner et al. 1997) [SEC PROJ erp.md]. The modern reading is a reward positivity that is missing after non-reward (Proudfit 2015) [ABS]. No verified measurement window was collected in this pass; set one in advance (FCz).
- Trials: about 20 per condition in young adults and about 50 in older adults (Marco-Pallarés et al. 2011) [ABS].
- Confound: the lab build no longer uses the delayed (800 ms) feedback display, so the outcome flash and its byte come with the outcome itself [PROJ eeg_lab_setup.txt]. For press outcomes the feedback-locked window then also holds the response-locked activity. The lab note already drops timeout, device_drop and no_signal rows [PROJ]. Check that response-locked averages for hits and misses do not differ in the FRN window, or add a press predictor in an rERP (my design).

### 7.5 CNV (Reaction, fixed 2.5 s foreperiod)

- S1 = 21 (the visible ready cue), S2 = the stimulus byte; catch trials carry 25 at the virtual onset [PROJ].
- Epoch -0.5 to +3.0 s around S1; baseline -0.2 to 0 s before S1; Cz, FCz, Fz. Early CNV about 0.5 to 1.5 s after S1; late CNV the last 0.5 s before S2 [SEC PROJ preparation_attention.md, citing Brunia and van Boxtel 2003].
- Filters: Section 5.2 (no high-pass, or an IIR at 0.01 to 0.05 Hz; low-pass 30 Hz; no detrend).
- Eyes: blinks and slow vertical eye drift during the wait; fit ICA on a 1 Hz copy and apply it to the unfiltered data [DOC MNE ICA tutorial].
- Trials: visible after 6 to 12 trials, plan for 30 or more [SEC PROJ preparation_attention.md, citing a 2024 Neuromethods chapter].
- The previous trial's post-movement beta rebound and slow potentials can sit in the pre-S1 baseline if the gap between trials is short [SEC PROJ preparation_attention.md].

### 7.6 LRP

- An LRP needs both hands. ERP CORE took contralateral minus ipsilateral at C3/C4 over left- and right-hand responses; epoch -0.8 to 0.2 s, baseline -0.8 to -0.6 s, window -0.1 to 0 s; 0.3 Hz high-pass [FT Zhang et al. 2024].
- Oostenveld et al. (2003) [ABS]: the double subtraction assumes hemispheric symmetry; analyse the single subtraction of the two lateralised conditions first. That also needs both hands.
- The lab's SRT uses one hand on purpose (Lum et al. 2025) [FT]; the project's two-hand layout runs only on the keyboard with one board [PROJ srt.md].
- With one hand, C3 minus C4 (right hand) is a lateralised motor wave that mixes response activity with any fixed hemispheric asymmetry. Report it as descriptive, not as an LRP (my inference from the double-subtraction logic).

### 7.7 Mu and beta ERD (Reaction, Chords)

- Lock: onset_offset_ms. Epochs about -3.5 to +2.0 s around the onset, padded for the wavelets, cropped after the TFR.
- Baseline: before S1 in Reaction (before the warning), at least three cycles of the lowest frequency (375 ms at 8 Hz) [FT part COBIDAS; arithmetic]. mode="percent" x 100 gives ERD percent (Pfurtscheller and Lopes da Silva 1999 [ABS]; percentage convention as described in [PROJ preparation_attention.md]). Mind the logratio bias (Section 5.7).
- Sites: C3 for the right hand and C4 for the left; CSD sharpens them [DOC compute_current_source_density].
- Spacing: the post-movement beta rebound takes seconds to resolve [SEC PROJ preparation_attention.md, citing a 2025 Frontiers paper]; Chords at speed smears ERD and rebound together.
- Trials: no verified minimum was found.

## 8. One session first: data quality

- mne.stats.erp.compute_sme(epochs, start=None, stop=None) returns the standardised measurement error per channel for the mean amplitude in a window; peak measures would need bootstrapping, which it does not do [DOC 1.13.2]. Luck et al. 2021, Psychophysiology 58(6):e13793 [SEC MNE docs and erpinfo.org]. Report SME and trial counts per measure for the feasibility session: they show whether one session resolves each component.
- Statistics within one person run across trials (for example cluster permutation tests, as the Lum papers did across participants [FT]). COBIDAS: correct for multiple comparisons, report the number of permutations, and avoid double dipping [FT part].

## 9. Pipelines and reporting

- MNE-BIDS: Appelhoff et al. 2019, JOSS 4:1896 [DOC]; also cite EEG-BIDS (Pernet et al. 2019, Scientific Data 6:103) [DOC link on the MNE-BIDS page; ABS record].
- mne-bids-pipeline 1.10.1 [DOC]: one configuration file per run of the pipeline; BIDS input only; stages init, preprocessing (data quality, filtering, artefact removal by ICA, SSP or regression, epochs, peak-to-peak rejection), sensor (evoked, decoding, time-frequency, covariance, group average) and source. The ERP CORE example uses one configuration per task and the montage name "standard_1005", which MNE 1.13 now flags as deprecated [CODE montage.py].
- My judgement: write a short, readable script for the first session (alignment is custom anyway); move to the pipeline once several sessions sit in BIDS.
- Reporting checklist, Keil et al. 2014 [ABS; checklist read through FieldTrip's copy, SEC]: sensor make and model; every sensor location including the reference; sampling rate; online filters with type, roll-off and cut-off; timing of all stimuli, responses and intervals; order of preprocessing steps; re-referencing with the sensors that form it; interpolation method; epoch length and baseline; artefact rejection with type and proportion; artefact correction with components removed per participant; offline filters with type, roll-off and cut-off; trials per condition (mean and range); measurement windows, baselines and sites with an a priori reason; spectral method, resolution, window and baseline unit.
- COBIDAS MEEG (Pernet et al. 2020) [FT part, accepted manuscript pages 1 to 16] adds: stimulus software type, version and operating system; how task events are determined; filter order or length, transition band, causality and direction; downsampling method; baseline method; explicit band edges; and BIDS for sharing.
- Cite MNE as Gramfort et al. 2013 plus the Zenodo DOI of the release used (1.13.2). MNE's cite page asks for Gramfort et al. 2014 only when its inverse-imaging methods are used, so it is optional for sensor-level work [DOC]. Also cite the method papers named in the docstrings (autoreject, ICLabel, PREP, Smith and Kutas).

## 10. Where sources disagree

1. High-pass for ERPs: 0.1 Hz or lower (MNE tutorial's reading of Acunzo 2012, Widmann 2015, Tanner 2015) against component-specific 0.2 to 0.9 Hz (Zhang et al. 2024), against "possibly 1 Hz" for evoked responses (mne-bids-pipeline docs, with a warning). Practice in the sequence-learning papers: 0.5 Hz (Kóbor 2019), 0.1 Hz (Lum 2023), 0.25 Hz (Lum 2024, 2025).
2. Baseline correction instead of a high-pass: Tanner et al. (2015, 2016) for; Maess et al. (2016) against, noting that a shared pre-stimulus effect gets copied into the post-stimulus period [DOC MNE tutorial summary].
3. ICA training high-pass: 1 Hz (MNE ICA docs; mne-bids-pipeline insists on at least 1 Hz) or 1 to 2 Hz (Winkler et al. 2015) against 0.1 Hz (ERP CORE as described by Zhang et al. 2024).
4. Notch at 50 Hz: never needed (BioSemi) against demonstrated and offered as routine (MNE tutorial, mne-bids-pipeline); used by Lum 2023 and Kóbor 2019, not by Lum 2024.
5. ERN trials: 6 to 8 errors (Olvet and Hajcak 2009; Pontifex et al. 2010) against more than 14 for test-retest reliability (Larson et al. 2010). The first two measure internal consistency and convergence with the grand average; Larson measured stability across sessions.
6. TF baseline: pre-stimulus, at least three cycles of the lowest frequency (COBIDAS) against the whole-epoch mean when trials have no rest (Lum 2023, 2024). dB/logratio as the convention against its negative bias (MNE docs citing Kinley et al. 2026) and its multiplicative assumption (Gyurkovics et al. 2021).
7. MNE's own docs against its code: the read_raw_bdf docstring shows reading CMS from bit 20 and suggests a 16-bit mask; the 1.13 code masks the stim channel to 17 bits on read, so bit 20 never appears.
8. Reference for ERN and P3: mastoids (ERP CORE, Lum 2023, Lum 2025) against average (Lum 2024, Kóbor 2019).
9. LRP: double subtraction (ERP CORE) against single subtraction first (Oostenveld et al. 2003). Both need two hands.
10. The brief describes Lum et al. 2023, 2024 and 2025 as written with Leow and Marinovic. Europe PMC lists Leow and Marinovic only on the 2025 paper (and on Leow et al. 2026, a behavioural SRT paper); the 2023 and 2024 papers are Deakin TMSi studies with other co-authors [ABS records; FT papers].

## 11. Pitfalls specific to this setup

1. Wrong mask: inputs 9 to 16 float high or carry F1 to F8 presses. Use mask=255 with mask_type="and" written out (old MNE defaulted to "not_and").
2. Do not expect CMS, battery or speed bits in MNE: they are masked off on read. Watch CMS/DRL in ActiView and note any out-of-range spell on the session sheet.
3. 255 on the line: the low byte reads 255 before the game opens the port. If ActiView's .cfg has PauseOn 255 and PauseOff 254 enabled, a box reset or a floating line could pause saving. Ask the lab to check the .cfg or set both to -1 [DOC BioSemi; risk is my inference].
4. Box glitches: if the Arduino's eight pins do not switch together, single-sample intermediate codes appear; min_duration about 2 ms plus the valid-code filter removes them. Check the raw Status channel around "EEG markers lost" moments in rehab.log.
5. Never trust the events.tsv onset or sample columns as EEG times: both are on the game's clock, from each block's first force sample.
6. Rows with failed = 1 or dropped = 1 never reached the amplifier; 240 and 241 are in the Status channel but not in events.tsv; restarted Force Pilot runs leave orphan 23 and 24 bytes; 219 marks an abandoned block.
7. difflib's default autojunk breaks alignment on long repetitive code runs (200 of 799 matched in the test); pass autojunk=False.
8. SRT response bytes go out at the trial's end. A response-locked epoch on the byte is wrong by hundreds of milliseconds. Use press_offset_ms or onset_offset_ms with pads, or (t_event - t_wire) with keys, less the box delay.
9. The box delay and the visual, tone and buzz delays are estimates until the photodiode, microphone and loopback runs. They bias latencies, not alignment.
10. Find events at the native rate; never resample Raw before epoching; ask the lab not to downsample in ActiView.
11. Read raw.info["sfreq"] from the file; do not assume 2048 Hz, and keep eeg.amplifier_rate_hz in eeg_lab.yaml in step with it.
12. Constant-interval SRT makes response-locked and next-flash activity collinear for overlap correction; prefer a jittered timing group for EEG sessions.
13. No clean pre-flash baseline in the SRT (0.65 to 0.9 s spacing); TF wavelets at 4 Hz span more than one trial.
14. One hand gives no LRP.
15. Immediate feedback puts the response inside the FRN window.
16. CNV: a 0.1 Hz high-pass removes about 80 percent of a 2.5 s shift (first-order arithmetic); MNE FIR filters at 0.01 Hz are 330 s long; detrending removes the ramp.
17. Unconnected EXG channels load as EEG and poison an average reference and ICA; set types or drop them first. Mastoid EXG channels have no positions in biosemi64, and ICLabel builds a 32 x 32 scalp image per component [DOC get_iclabel_features], so every channel inside the ICA needs a position. Give the mastoids approximate positions or keep them out of the ICA (type misc) until the final re-reference (my inference). Interpolation and RANSAC also need positions [DOC].
18. ICLabel needs an average reference, 1 to 100 Hz and extended Infomax; fit and apply ICA under the same reference, then re-reference.
19. Montage: biosemi64 uses 10-20 labels; ActiView files may use A1 to B32. standard_1005 now warns in MNE 1.13 and will be removed in 1.14.
20. Analysis needs Python 3.11 or newer (MNE 1.13); the lab's PsychoPy Python may be 3.10.
21. Preloading a full 48-minute, 73-channel file at 2048 Hz takes about 3.4 GB of RAM.
22. Small error counts: SRT, Adaptive and Chords may give fewer than the 6 to 8 errors a stable ERN needs per condition.

## 12. To confirm with the lab

- Saved sampling rate, and whether ActiView downsamples on save.
- Cap size and layout (10-20 or ABC), channel labels in the BDF, and what EXG1 to EXG8 carry (mastoids, EOG, unused).
- Whether PauseOn and PauseOff are enabled in the ActiView .cfg, and whether saving is ever paused mid-session.
- The lab's usual offline reference, filters and artefact pipeline (the Lum papers used RELAX in EEGLAB on TMSi data).
- Which SRT timing group the EEG sessions use, and whether participants press keys or pads.
- A loopback or photodiode measure of the box delay; photodiode and microphone runs for the screen and tone delays.

## 13. Code sketch (MNE 1.13.2; untested here)

```python
import difflib
import numpy as np
import pandas as pd
import mne

# 1. Load
raw = mne.io.read_raw_bdf("P07_2026-09-24.bdf", stim_channel="auto",
                          infer_types=False, preload=False)
sfreq = raw.info["sfreq"]                       # never assume 2048
raw.set_channel_types({"EXG3": "eog", "EXG4": "eog", "EXG5": "eog", "EXG6": "eog"})  # per lab wiring
raw.drop_channels(["EXG7", "EXG8"])             # if unconnected
raw.set_montage("biosemi64", on_missing="warn")  # after renaming A1..B32 if needed

# 2. Events at the native rate
ev = mne.find_events(raw, stim_channel="Status", mask=255, mask_type="and",
                     consecutive=True, min_duration=0.002, shortest_event=2)
ev = ev[np.isin(ev[:, 2], VALID_CODES)]

# 3. Align one block (sent = events.tsv rows, failed == 0 and dropped == 0)
def align_block(sent, recv, sfreq, tol_s):
    sm = difflib.SequenceMatcher(a=list(sent["value"]), b=list(recv[:, 2]), autojunk=False)
    pairs = [(i + k, j + k) for i, j, n in sm.get_matching_blocks() for k in range(n)]
    ia, ib = map(np.array, zip(*pairs))
    t_game = sent["t_wire"].to_numpy()[ia]
    t_eeg = recv[ib, 0] / sfreq
    ok = np.r_[True, np.abs(np.diff(t_eeg) - np.diff(t_game)) <= tol_s]
    b, a = np.polyfit(t_game[ok], t_eeg[ok], 1)
    resid = t_eeg[ok] - (a + b * t_game[ok])
    return ia[ok], ib[ok], a, b, resid, 1e6 * abs(1 - b)   # last value: drift in ppm

# 4. Per-event shifts (press-locked shown); box_delay_ms from a loopback measure
#    sample_press = byte_sample + round(sfreq * (press_offset_ms - box_delay_ms) / 1000)

# 5. ICA on a copy: average reference, 1 to 100 Hz, extended Infomax via Picard
raw.load_data()
raw.set_eeg_reference("average")
raw_ica = raw.copy().filter(1.0, 100.0)
ica = mne.preprocessing.ICA(n_components=None, method="picard",
                            fit_params=dict(ortho=False, extended=True), rng=97)
scalp = mne.pick_types(raw_ica.info, eeg=True,
                       exclude=raw_ica.info["bads"] + ["EXG1", "EXG2"])  # mastoids have no positions
ica.fit(raw_ica, picks=scalp, reject_by_annotation=True)
# from mne_icalabel import label_components
# labels = label_components(raw_ica, ica, method="iclabel")

# 6. Analysis copy (ERN example): filter, apply ICA, then re-reference
raw_ern = raw.copy().filter(0.4, None, method="iir")   # check with mne.viz.plot_filter
ica.apply(raw_ern)
raw_ern.set_eeg_reference(["EXG1", "EXG2"])             # if these were the mastoids
epochs = mne.Epochs(raw_ern, ev_onset_locked, event_id=ern_ids, tmin=-0.6, tmax=0.4,
                    baseline=(-0.4, -0.2), metadata=md, preload=True)
sme = mne.stats.erp.compute_sme(epochs["wrong"], start=0.0, stop=0.1)

# 7. SRT overlap: regression ERPs
# from mne.stats import linear_regression_raw
# evokeds = linear_regression_raw(raw_srt, ev_srt, event_id=srt_ids,
#                                 tmin=dict(...), tmax=dict(...),
#                                 reject=dict(eeg=150e-6), tstep=1.0, decim=8)

# 8. ERD
# tfr = epochs_erd.compute_tfr(method="morlet", freqs=np.arange(8, 31), n_cycles=np.arange(8, 31) / 2,
#                              average=True, decim=8)
# tfr.apply_baseline(baseline=(-3.5, -3.0), mode="percent")   # x 100 = ERD percent
```

## 14. References

Software and documentation

- MNE-Python 1.13.2 documentation, https://mne.tools/stable/ : read_raw_bdf, find_events, Epochs, Raw.resample, create_filter, ICA, set_eeg_reference tutorial, filtering tutorials, ICA tutorial, ERP tutorial, TF tutorial, morlet, rescale, linear_regression_raw and its example, realign_raw, shift_time_events, make_metadata, annotate_break, compute_current_source_density, compute_sme, make_standard_montage, changelog v1.13, cite page [DOC]
- MNE source, branch maint/1.13: mne/io/edf/edf.py, mne/event.py, mne/preprocessing/realign.py, mne/baseline.py, mne/channels/montage.py, mne/channels/_standard_montage_utils.py, mne/channels/data/montages/biosemi64.txt [CODE]
- MNE 0.14 find_events page, https://www.nmr.mgh.harvard.edu/mne/0.14/generated/mne.find_events.html [DOC]
- mne-bids 0.20.0 docs (read_raw_bids, write_raw_bids, index) and mne_bids/read.py on main [DOC; CODE]
- mne-bids-pipeline 1.10.1 docs: ERP CORE example, filter settings, ICA and SSP settings, processing steps [DOC]
- mne-icalabel 0.10.0 docs: label_components, iclabel_label_components, cite page [DOC]
- autoreject 0.5.1 docs: index, AutoReject, workflow example, FAQ [DOC]
- pyprep 0.9.0 docs: index, NoisyChannels [DOC]
- BioSemi FAQs: https://www.biosemi.com/faq/trigger_signals.htm , https://www.biosemi.com/faq/cms&drl.htm , https://www.biosemi.com/faq/file_format.htm , https://www.biosemi.com/faq/adjust_filter.htm , https://biosemi.com/faq/adjust_samplerate.htm , https://www.biosemi.com/headcap.htm [DOC]
- FieldTrip, Getting started with BioSemi, https://www.fieldtriptoolbox.org/getting_started/eeg/biosemi/ [DOC]
- BIDS specification, events, https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/events.html [DOC]
- Lab Streaming Layer, time synchronisation, https://labstreaminglayer.readthedocs.io/info/time_synchronization.html [DOC]
- Unfold.jl documentation (juliahub mirror), https://docs.juliahub.com/Unfold/zdLTm/0.6.1 [DOC, from search excerpt]
- Smith, L. (2005). EEGLAB mailing list post on BioSemi Status bits, https://sccn.ucsd.edu/pipermail/eeglablist/2005/000485.html [SEC, not BioSemi]

Papers

- Appelhoff, S., et al. (2019). MNE-BIDS: Organizing electrophysiological data into the BIDS format and facilitating their analysis. JOSS 4:1896. doi:10.21105/joss.01896 [DOC]
- Bigdely-Shamlo, N., Mullen, T., Kothe, C., Su, K. M., Robbins, K. A. (2015). The PREP pipeline. Front Neuroinform 9:16. doi:10.3389/fninf.2015.00016 [ABS]
- Cohen, J., Polich, J. (1997). On the number of trials needed for P300. Int J Psychophysiol 25(3):249-255. doi:10.1016/s0167-8760(96)00743-x [ABS]
- Ehinger, B. V., Dimigen, O. (2019). Unfold: an integrated toolbox for overlap correction, non-linear modeling, and regression-based EEG analysis. PeerJ 7:e7838. doi:10.7717/peerj.7838 [FT, PMC6815663]
- Fischer, A. G., Klein, T. A., Ullsperger, M. (2017). Comparing the error-related negativity across groups: the impact of error- and trial-number differences. Psychophysiology 54(7):998-1009. doi:10.1111/psyp.12863 [ABS]
- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Front Neurosci 7:267. doi:10.3389/fnins.2013.00267 [DOC cite page]
- Gramfort, A., et al. (2014). MNE software for processing MEG and EEG data. NeuroImage 86:446-460. doi:10.1016/j.neuroimage.2013.10.027 [DOC cite page]
- Gyurkovics, M., Clements, G. M., Low, K. A., Fabiani, M., Gratton, G. (2021). The impact of 1/f activity and baseline correction on the results and interpretation of time-frequency analyses of EEG/MEG data: a cautionary tale. NeuroImage 237:118192. doi:10.1016/j.neuroimage.2021.118192 [ABS]
- Jas, M., Engemann, D. A., Bekhti, Y., Raimondo, F., Gramfort, A. (2017). Autoreject: automated artifact rejection for MEG and EEG data. NeuroImage 159:417-429. doi:10.1016/j.neuroimage.2017.06.030 [ABS]
- Kappenman, E. S., Farrens, J. L., Zhang, W., Stewart, A. X., Luck, S. J. (2021). ERP CORE: an open resource for human event-related potential research. NeuroImage 225:117465. doi:10.1016/j.neuroimage.2020.117465 [SEC Zhang et al. 2024; record via erpinfo.org]
- Keil, A., et al. (2014). Committee report: publication guidelines and recommendations for studies using electroencephalography and magnetoencephalography. Psychophysiology 51(1):1-21. doi:10.1111/psyp.12147 [ABS; checklist via FieldTrip, SEC]
- Kinley, I., Roberts, R. P., Meltzer, J. A., Addis, D. R. (2026). Spectral change or Jensen gap? Log-ratio baseline correction for time-frequency M/EEG is negatively biased. J Neurosci Methods, 110826. [SEC MNE TF tutorial; not found by search]
- Kóbor, A., et al. (2019). Tracking the implicit acquisition of nonadjacent transitional probabilities by ERPs. Mem Cognit 47(8):1546-1566. doi:10.3758/s13421-019-00949-x [FT, PMC6823303]
- Larson, M. J., Baldwin, S. A., Good, D. A., Fair, J. E. (2010). Temporal stability of the error-related negativity (ERN) and post-error positivity (Pe): the role of number of trials. Psychophysiology 47(6):1167-1171. doi:10.1111/j.1469-8986.2010.01022.x [ABS]
- Leow, L.-A., Lum, J., Johnson, S., Corti, E., Marinovic, W. (2026). Musical training increases anticipatory responding and predictive control in sequence learning. Psychol Res 90(4):124. doi:10.1007/s00426-026-02333-2 [FT, PMC13328134; behavioural, no EEG]
- Li, A., et al. (2022). MNE-ICALabel: automatically annotating ICA components with ICLabel in Python. JOSS 7(76):4484. doi:10.21105/joss.04484 [DOC cite page]
- Luck, S. J., Stewart, A. X., Simmons, A. M., Rhemtulla, M. (2021). Standardized measurement error: a universal metric of data quality for averaged event-related potentials. Psychophysiology 58(6):e13793. doi:10.1111/psyp.13793 [SEC MNE compute_sme page]
- Lum, J. A. G., Clark, G. M., Barhoun, P., Hill, A. T., Hyde, C., Wilson, P. H. (2023). Neural basis of implicit motor sequence learning: modulation of cortical power. Psychophysiology 60(2):e14179. doi:10.1111/psyp.14179 [FT, PMC10078012, Methods]
- Lum, J. A. G., Barham, M. P., Hyde, C., Hill, A. T., White, D. J., Hughes, M. E., Clark, G. M. (2024). Top-down and bottom-up oscillatory dynamics regulate implicit visuomotor sequence learning. Cereb Cortex 34(7):bhae266. doi:10.1093/cercor/bhae266 [FT, PMC11267723, Methods]
- Lum, J. A. G., Hamilton, K. M., Leow, L.-A., Marinovic, W., et al. (2025). Atypical beta oscillatory dynamics are related to poor procedural learning in children with developmental coordination disorder. Dev Sci 28(4):e70031. doi:10.1111/desc.70031 [FT, PMC12096045, Methods]
- Marco-Pallarés, J., Cucurell, D., Münte, T. F., Strien, N., Rodriguez-Fornells, A. (2011). On the number of trials needed for a stable feedback-related negativity. Psychophysiology 48(6):852-860. doi:10.1111/j.1469-8986.2010.01152.x [ABS]
- Olvet, D. M., Hajcak, G. (2009). The stability of error-related brain activity with increasing trials. Psychophysiology 46(5):957-961. doi:10.1111/j.1469-8986.2009.00848.x [ABS]
- Oostenveld, R., Stegeman, D. F., Praamstra, P., van Oosterom, A. (2003). Brain symmetry and topographic analysis of lateralized event-related potentials. Clin Neurophysiol 114(7):1194-1202. doi:10.1016/s1388-2457(03)00059-2 [ABS]
- Pernet, C. R., Appelhoff, S., Gorgolewski, K. J., Flandin, G., Phillips, C., Delorme, A., Oostenveld, R. (2019). EEG-BIDS, an extension to the brain imaging data structure for electroencephalography. Sci Data 6:103. doi:10.1038/s41597-019-0104-8 [ABS]
- Pernet, C., Garrido, M. I., Gramfort, A., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nat Neurosci 23(12):1473-1483. doi:10.1038/s41593-020-00709-0 [FT part, accepted manuscript pages 1 to 16, Aalto repository]
- Pfurtscheller, G., Lopes da Silva, F. H. (1999). Event-related EEG/MEG synchronization and desynchronization: basic principles. Clin Neurophysiol 110(11):1842-1857. doi:10.1016/s1388-2457(99)00141-8 [ABS]
- Pion-Tonachini, L., Kreutz-Delgado, K., Makeig, S. (2019). ICLabel: an automated electroencephalographic independent component classifier, dataset, and website. NeuroImage 198:181-197. doi:10.1016/j.neuroimage.2019.05.026 [DOC cite page]
- Pontifex, M. B., et al. (2010). On the number of trials necessary for stabilization of error-related brain activity across the life span. Psychophysiology 47(4):767-773. doi:10.1111/j.1469-8986.2010.00974.x [ABS]
- Proudfit, G. H. (2015). The reward positivity: from basic research on reward to a biomarker for depression. Psychophysiology 52(4):449-459. doi:10.1111/psyp.12370 [ABS]
- Smith, N. J., Kutas, M. (2015). Regression-based estimation of ERP waveforms: I. The rERP framework. Psychophysiology 52:157-168. doi:10.1111/psyp.12317 [SEC Part II references]
- Smith, N. J., Kutas, M. (2015). Regression-based estimation of ERP waveforms: II. Nonlinear effects, overlap correction, and practical considerations. Psychophysiology 52(2):169-181. doi:10.1111/psyp.12320 [FT, author copy at vorpus.org]
- Tanner, D., Morgan-Short, K., Luck, S. J. (2015). How inappropriate high-pass filters can produce artifactual effects and incorrect conclusions in ERP studies of language and cognition. Psychophysiology 52(8):997-1009. doi:10.1111/psyp.12437 [ABS; recommendation via MNE tutorial, SEC]
- Widmann, A., Schröger, E., Maess, B. (2015). Digital filter design for electrophysiological data: a practical approach. J Neurosci Methods 250:34-46. doi:10.1016/j.jneumeth.2014.08.002 [SEC MNE tutorial]
- Winkler, I., Debener, S., Müller, K.-R., Tangermann, M. (2015). On the influence of high-pass filtering on ICA-based artifact reduction in EEG-ERP. Proc IEEE EMBC 2015:4101-4105. doi:10.1109/EMBC.2015.7319296 [ABS]
- Zhang, G., Garrett, D. R., Luck, S. J. (2024). Optimal filters for ERP research II: recommended settings for seven common ERP components. Psychophysiology 61(6):e14530. doi:10.1111/psyp.14530 [FT, PMC11096077, Tables 1 and 2]
- Also cited in MNE's tutorial only [SEC]: Acunzo, MacKenzie and van Rossum 2012 (J Neurosci Methods 209:212-218, doi:10.1016/j.jneumeth.2012.06.011); Maess, Schröger and Widmann 2016 (J Neurosci Methods 266:164-165, doi:10.1016/j.jneumeth.2015.12.003); Tanner, Norton, Morgan-Short and Luck 2016 (J Neurosci Methods 266:166-170, doi:10.1016/j.jneumeth.2016.01.002); Kayser and Tenke 2015 (Int J Psychophysiol 97:171-173, doi:10.1016/j.ijpsycho.2015.06.001); Perrin et al. 1989 (Electroencephalogr Clin Neurophysiol 72:184-187, doi:10.1016/0013-4694(89)90180-6).
- Cited through the project's notes only [SEC PROJ]: Miltner, Braun and Coles 1997; Overbeek, Nieuwenhuis and Ridderinkhof 2005; Brunia and van Boxtel 2003; Boudewyn et al. 2018; the 2024 Neuromethods CNV chapter; the 2025 Frontiers PMBR paper.

## 15. Plain-English glossary (for teaching)

- Status channel: the amplifier's extra channel that records the trigger lines as a number at every sample. Like a logic analyser channel recorded beside the EEG.
- CMS/DRL: BioSemi's active "ground" pair. CMS is the point every channel is measured against; DRL drives the body towards the amplifier's reference voltage, like a feedback loop holding a setpoint. The file therefore holds unreferenced signals, and a reference must be picked offline.
- Re-reference: subtract a chosen signal (one electrode, the mastoids, or the average) from every channel.
- High-pass / low-pass: filters that remove slow drift / fast noise. Too strong a high-pass bends slow brain waves (like a coupling capacitor that is too small).
- ICA: splits the recording into independent sources so blink and eye-movement sources can be removed and the rest put back.
- Epoch: a window of EEG cut around an event, for example -0.2 to 0.8 s around a flash.
- Baseline correction: subtract the mean of a quiet window before the event so all epochs start from zero.
- ERP: the average of many epochs, which cancels activity not locked to the event.
- rERP / deconvolution: a regression that separates responses to events that come so close together that their ERPs overlap.
- ERN, Pe, FRN, P3, N2, CNV, LRP: named ERP deflections (error, error awareness, feedback, target evaluation, conflict or mismatch, preparation over a wait, hand-specific preparation).
- ERD: event-related desynchronisation, the drop in mu (about 8 to 13 Hz) and beta (about 13 to 30 Hz) power over motor cortex around a movement.
- SME: standardised measurement error, the standard error of a single person's averaged ERP score; smaller means cleaner data.
