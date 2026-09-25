# Force Pilot and Parkinson's disease: verified literature base

Prepared 25 September 2026 for the Finger Rehab thesis (Curtin). Scope: the Parkinson's disease (PD) literature behind one game mode, Force Pilot: isometric single-finger force tracking through a scrolling corridor, force expressed as percent of the finger's own max press, raw force saved at 200 Hz for all four pads.

Framing that applies to every section: the thesis study is a healthy-adult baseline (young volunteers, one 60 minute sitting, right-hand board). Nothing here shows that Force Pilot helps people with PD. The PD papers justify which measures are computed, what a healthy hand should score, and what a later PD study would need.

How each source was checked:

- PubMed E-utilities (esearch, esummary, efetch), run 25 September 2026. Every entry in A1 to A7 has a PubMed record and its abstract was read. A8 entries were checked for bibliographic details only.
- Where the paper is open access, the full text was pulled from Europe PMC and any number quoted from tables was read there ("full text read").
- Numbers appear only where they were read in an abstract or full text. Anything I derived is labelled "arithmetic".
- One paper found only on Crossref is listed under E3 and is not used as evidence.

Project material read first (nothing was modified): `app/docs/research/new_modes/force-control.md`, `movement-disorders.md`, `ranked.md`, `app/docs/research/healthy_baseline_study.txt` (Section 1.8, checks F1 to F4), the `force_pilot.py` docstring and ladder table, the preview comment in `force_pilot_screen.py`, the force_pilot block of `config/default.yaml`, and the Force Pilot functions in `analysis/session_analysis.ipynb`.

Short keys such as [Davidson 2026] are used in Sections B to E.

---

## A. Verified reference list

Each entry: citation and identifiers; study type and sample; finding in my own words; confidence and how it was verified.

### A1. Force control deficits in PD on finger and grip isometric tasks

**A1.1 [Davidson 2026]** Davidson S, Learman K, Rosenfeldt AB, Zimmerman E, Alberts JL. Parkinson's disease impairs grip force release during a sinusoidal force tracking task. Exp Brain Res. 2026;244(4):46. PMID 41706132. DOI 10.1007/s00221-026-07241-w. PMC12916958.
- Cross-sectional. 10 young (18 to 28 y), 10 older, 10 PD tested OFF (12 h withdrawal; MDS-UPDRS-III median 29). Precision grip, 0.2 Hz sine between 10 and 30% MVC, 32 s trials, 10 trials, about 4 s of upcoming target visible.
- PD were worst overall. Error (RRMSE) showed no group by phase interaction, but time within ±5% of target dropped more in release than in generation for PD against young adults. Fitted sine amplitude fell short of target by 16.6 ± 4.1% (young), 26.6 ± 9.4% (older) and 39.3 ± 11.5% (PD). Young adults were slightly better in release than generation (RRMSE 0.38 vs 0.42; %TWR 52.4 vs 47.0).
- Confidence: high. Full text read (Tables 1 and 2). Confirms the force-control.md entry.

**A1.2 [Davidson 2025 PD]** Davidson S, Learman K, Zimmerman E, Rosenfeldt AB, Alberts JL. Grip force release is impaired in parkinson's disease during a force tracking task. Exp Brain Res. 2025;243(1):16 (online 5 Dec 2024). PMID 39636326. DOI 10.1007/s00221-024-06966-w. PMC13041725.
- Cross-sectional. 10 PD (H&Y I to III, OFF 12 h) vs 10 age-matched controls. Ramp 0 to 35% MVC in 3.3 s (about 10% MVC/s), 5 s hold, release in 3.3 s, then a terminal phase at 0%.
- PD had more error, less time near target and more trial-to-trial variability in release and in the terminal phase (force still being let go after the target reached zero). Hedges g: release RRMSE -1.11, release %TWR 1.24, terminal RRMSE -1.16, terminal trial-to-trial SD of RRMSE -1.27. Terminal %TWR 81.4 (controls) vs 51.0 (PD).
- Confidence: high. Full text read. This is the "authors not confirmed" entry in movement-disorders.md; the authors cite it as 2025.

**A1.3 [Davidson 2024 OA]** Davidson S, Learman K, Zimmerman E, Rosenfeldt AB, Koop M, Alberts JL. Older adults are impaired in the release of grip force during a force tracking task. Exp Brain Res. 2024;242(3):665-674. PMID 38246931. DOI 10.1007/s00221-023-06770-y. PMC10894767.
- 10 young (22.6 y) vs 10 older (67.7 y), same ramp-hold-release task.
- Older adults were disproportionately worse in release (release RRMSE g 2.69). Young adults: RRMSE generation 0.47 ± 0.16, hold 0.24 ± 0.07, release 0.39 ± 0.06; %TWR 44.3 ± 14.1, 75.4 ± 14.3, 50.1 ± 6.5.
- Confidence: high. Full text read. This is the PMC10894767 entry in force-control.md.

**A1.4 [Chung 2023]** Chung JW, Knight CA, Bower AE, Martello JP, Jeka JJ, Burciu RG. Rate control deficits during pinch grip and ankle dorsiflexion in early-stage Parkinson's disease. PLoS One. 2023;18(3):e0282203. PMID 36867628. DOI 10.1371/journal.pone.0282203. PMC9983837.
- 20 early PD (OFF overnight, more affected side) vs 21 healthy older adults. 2 s pulses to 15% MVC produced as fast as possible, 1 s rest.
- In the hand only relaxation was slower in PD (-43.2 ± 12.1 vs -57.4 ± 12.2 %MVC/s). Rate of rise (36.3 vs 38.3 %MVC/s) and force variability did not differ. Slower hand relaxation went with worse rhythm on a sensor-based hand rating.
- Confidence: high. Full text read (Table 2).

**A1.5 [Neely 2013]** Neely KA, Planetta PJ, Prodoehl J, Corcos DM, Comella CL, Goetz CG, et al. Force control deficits in individuals with Parkinson's disease, multiple systems atrophy, and progressive supranuclear palsy. PLoS One. 2013;8(3):e58403. PMID 23505500. DOI 10.1371/journal.pone.0058403. PMC3594313.
- 12 PD, 12 MSA-P, 8 PSP, 12 controls, all OFF. Ten 2 s precision-grip pulses at 15% MVC with 1 s rest.
- All patient groups were slower to raise and lower force and held pulses longer. Extra, unintended pulses were specific to PSP.
- Confidence: high. Full text read; rates appear only in figures, so no values quoted.

**A1.6 [Howard 2022]** Howard SL, Grenet D, Bellumori M, Knight CA. Measures of motor segmentation from rapid isometric force pulses are reliable and differentiate Parkinson's disease from age-related slowing. Exp Brain Res. 2022;240(7-8):2205-2217. PMID 35768733. DOI 10.1007/s00221-022-06398-4.
- 10 PD (H&Y below 3) vs published older-adult reference data. About 87 rapid index finger abduction pulses up to 65% of max.
- Breaks in the force-time curve (segmentation) were reliable across days (the paper's test was ICC above 0.8) and separated PD from older adults with large effects (d above 0.8). More segmentation went with slower rates (ρ above 0.8).
- Confidence: medium. Abstract only (paywalled); individual ICCs not quoted.

**A1.7 [Daniels 2024]** Daniels RJ, Grenet D, Knight CA. Impaired performance of rapid grip in people with Parkinson's disease and motor segmentation. Hum Mov Sci. 2024;95:103201. PMID 38507858. DOI 10.1016/j.humov.2024.103201.
- 22 PD vs young and older adults. Rapid handgrip pulses to 20 to 60% MVC with EMG.
- PD had slower rise and relaxation and longer pulses. 6 of 22 showed segmented force curves, which tracked extra EMG bursts.
- Confidence: medium. Abstract only.

**A1.8 [Stelmach 1989]** Stelmach GE, Teasdale N, Phillips J, Worringham CJ. Force production characteristics in Parkinson's disease. Exp Brain Res. 1989;76(1):165-172. PMID 2753097. DOI 10.1007/BF00253633.
- PD, older and young adults; fast isometric presses to 15, 30, 45, 60% of max.
- Spread of peak force across trials in PD matched controls, but single force-time curves were irregular with changing rate, and force onset was slow.
- Confidence: medium. Abstract only.

**A1.9 [Wing 1988]** Wing AM. A comparison of the rate of pinch grip force increases and decreases in parkinsonian bradykinesia. Neuropsychologia. 1988;26(3):479-482. PMID 3374806. DOI 10.1016/0028-3932(88)90100-5.
- Two untreated asymmetric cases.
- In the more affected hand, force decreases were slowed more than increases. The earliest release-specific report; historical weight only.
- Confidence: medium. Abstract only.

**A1.10 [Jordan 1992]** Jordan N, Sagar HJ, Cooper JA. A component analysis of the generation and release of isometric force in Parkinson's disease. J Neurol Neurosurg Psychiatry. 1992;55(7):572-576. PMID 1640233. DOI 10.1136/jnnp.55.7.572. PMC489168.
- PD cohort including de novo patients followed after treatment started.
- Latency and rate were impaired for both force onset and release. Rate of force change tracked clinical motor disability, and treatment sped release but not latency.
- Confidence: medium. Abstract only.

**A1.11 [Kunesch 1995]** Kunesch E, Schnitzler A, Tyercha C, Knecht S, Stelmach G. Altered force release control in Parkinson's disease. Behav Brain Res. 1995;67(1):43-49. PMID 7748499. DOI 10.1016/0166-4328(94)00111-r.
- PD vs controls on visually guided isometric tracking and aiming.
- Most tasks were near normal. The clearest deficit was imprecise release of a produced force, plus trouble holding a target for 30 s.
- Confidence: medium. Abstract only.

**A1.12 [Vaillancourt 2001a]** Vaillancourt DE, Slifkin AB, Newell KM. Visual control of isometric force in Parkinson's disease. Neuropsychologia. 2001;39(13):1410-1418. PMID 11585609. DOI 10.1016/s0028-3932(01)00061-6.
- 8 PD vs 8 matched controls. Precision grip holds at 5, 25, 50% MVC for 20 s; in some trials vision was removed after 8 s.
- With vision, PD held force like controls. Without vision both groups drifted down, but PD decayed further and faster.
- Confidence: medium. Abstract only.

**A1.13 [Vaillancourt 2001b]** Vaillancourt DE, Slifkin AB, Newell KM. Regularity of force tremor in Parkinson's disease. Clin Neurophysiol. 2001;112(9):1594-1603. PMID 11514241. DOI 10.1016/s1388-2457(01)00593-4.
- 8 young, 8 older, 8 PD. Grip holds at 5, 25, 50% MVC, with and without vision.
- Tremor amplitude and peak frequency did not differ between groups. PD force output was more regular (lower approximate entropy), and regularity tracked UPDRS motor score (r² = 0.71).
- Confidence: medium. Abstract only.

**A1.14 [Vaillancourt 2002]** Vaillancourt DE, Slifkin AB, Newell KM. Inter-digit individuation and force variability in the precision grip of young, elderly, and Parkinson's disease participants. Motor Control. 2002;6(2):113-128. PMID 12122222. DOI 10.1123/mcj.6.2.113.
- 7 young, 7 older, 7 PD. Holds at 5, 25, 50% MVC with and without vision.
- PD were more variable (SD and RMSE) than both control groups, and thumb and index acted less independently. Less independence went with more variability.
- Confidence: medium. Abstract only.

**A1.15 [Tobin 2025]** Tobin ER, Delmas S, Kim JJ, Hubbard JC, Yacoubi B, Lou X, et al. Force control deficits in rapid eye movement behavior disorder and Parkinson's disease. Clin Neurophysiol. 2025;176:2110763. PMID 40472441. DOI 10.1016/j.clinph.2025.2110763. PMC12320221.
- 27 controls, 37 REM sleep behaviour disorder (RBD), 37 early PD (H&Y 2 or less when medicated). Index finger abduction held at 15% MVC for 120 s (20 to 40 s analysed), plus fast reverse-at-target pulses.
- Finger CV of force: controls 3.39 ± 1.86%, PD 5.67 ± 3.57%, RBD 9.85 ± 9.74%. PD were slower to raise and relax force in the fast task. In PD, finger CV correlated weakly with the MDS-UPDRS-III bradykinesia subscore (r = 0.335).
- Confidence: high. Full text read. Medication state during testing was not stated in the text I read.

**A1.16 [Olamazadeh 2026]** Olamazadeh A, Brenner S, Souza de Oliveira D, Regensburger M, Del Vecchio A, Kinfe TM. Differential Effects of High and Low Frequency Subthalamic Nucleus Deep Brain Stimulation on Force Steadiness in Patients with Parkinson's Disease: An Exploratory Study. Neurol Ther. 2026;15(4):1931-1943. PMID 42252378. DOI 10.1007/s40120-026-00976-2. PMC13396081.
- 10 PD with STN DBS. Pinch tracking at 10% and 20% MVC under four stimulation settings.
- Patients with MDS-UPDRS-III above 25 had higher CoV than milder patients at both levels (Cliff's δ 0.83 and 0.92). In that subgroup 130 Hz stimulation lowered CoV against DBS off.
- Confidence: medium. Abstract only; exploratory and small.

**A1.17 [Ko 2015]** Ko NH, Laine CM, Fisher BE, Valero-Cuevas FJ. Force Variability during Dexterous Manipulation in Individuals with Mild to Moderate Parkinson's Disease. Front Aging Neurosci. 2015;7:151. PMID 26321947. DOI 10.3389/fnagi.2015.00151. PMC4530309.
- 20 PD. Compressing a buckling-prone spring at under 3 N.
- The more affected hand produced less force and less low-frequency (below 4 Hz) variability. More low-frequency variability went with better UPDRS scores, the reverse of the usual reading.
- Confidence: medium. Abstract only.

**A1.18 [Poon 2011]** Poon C, Robichaud JA, Corcos DM, Goldman JG, Vaillancourt DE. Combined measures of movement and force variability distinguish Parkinson's disease from essential tremor. Clin Neurophysiol. 2011;122(11):2268-2275. PMID 21570904. DOI 10.1016/j.clinph.2011.04.014. PMC3183282.
- 12 PD vs 12 essential tremor.
- Force variability was worse in essential tremor than PD; PD were worse on movement deceleration. Combined measures separated the groups (AUC up to 0.99).
- Confidence: medium. Abstract only.

**A1.19 [Pradhan 2010]** Pradhan SD, Brewer BR, Carvell GE, Sparto PJ, Delitto A, Matsuoka Y. Assessment of fine motor control in individuals with Parkinson's disease using force tracking with a secondary cognitive task. J Neurol Phys Ther. 2010;34(1):32-40. PMID 20212366. DOI 10.1097/NPT.0b013e3181d055a6.
- 30 PD vs 30 age-similar controls. Thumb-index pinch tracking of a sine or pseudorandom target, with and without counting backwards.
- PD had larger RMSE, more tremor and longer lag, and the gaps widened under cognitive load.
- Confidence: medium. Abstract only; protocol details from [Brewer 2009].

**A1.20 [Brewer 2009]** Brewer BR, Pradhan S, Carvell G, Delitto A. Application of modified regression techniques to a quantitative assessment for the motor signs of Parkinson's disease. IEEE Trans Neural Syst Rehabil Eng. 2009;17(6):568-575. PMID 19884100. DOI 10.1109/TNSRE.2009.2034461. PMC4894031.
- 26 PD with complete data from the same protocol: sine with a 7.5 s period and 12.5 s of preview, pseudorandom with no preview, 3 min per waveform at 100 Hz.
- Tremor power from 2 to 8 Hz, RMSE and lag predicted UPDRS within about 3.5 points and explained about 76% of its variance. The authors note RMSE was dominated by undershooting the target wave.
- Confidence: high. Full text read. 36 predictors on 26 people, so overfitting is a real risk.

**A1.21 [Pradhan 2015]** Pradhan S, Scherer R, Matsuoka Y, Kelly VE. Grip force modulation characteristics as a marker for clinical disease progression in individuals with Parkinson disease: case-control study. Phys Ther. 2015;95(3):369-379. PMID 25476717. DOI 10.2522/ptj.20130570. PMC4757638.
- 14 early PD vs 14 older adults. Instrumented twist-cap task, single and dual task.
- PD showed more movement arrests (pauses) in both grips, and more arrests went with worse motor severity.
- Confidence: medium. Abstract only.

**A1.22 [Park 2012]** Park J, Wu YH, Lewis MM, Huang X, Latash ML. Changes in multifinger interaction and coordination in Parkinson's disease. J Neurophysiol. 2012;108(3):915-924. PMID 22552184. DOI 10.1152/jn.00043.2012. PMC3424084.
- 10 mostly early PD vs 11 controls. Single and multi-finger pressing on four finger sensors.
- PD had lower finger strength, more unintended force in non-task fingers (enslaving), weaker multi-finger synergies, delayed anticipatory adjustments; half could not do the 2 Hz cyclic task.
- Confidence: medium. Abstract only. Directly relevant because the rig has one pad under each of four fingers.

**A1.23 [Fellows 1998]** Fellows SJ, Noth J, Schwarz M. Precision grip and Parkinson's disease. Brain. 1998;121(9):1771-1784. PMID 9762964. DOI 10.1093/brain/121.9.1771.
- 16 PD plus 4 hemiparkinsonian vs 12 controls. Grip-lift and hold with load changes.
- PD used abnormally high grip forces with normal grip-to-load ratios, and built force slowly before lift-off.
- Confidence: medium. Abstract only.

**A1.24 [Fellows 2004]** Fellows SJ, Noth J. Grip force abnormalities in de novo Parkinson's disease. Mov Disord. 2004;19(5):560-565. PMID 15133821. DOI 10.1002/mds.10710.
- 6 newly diagnosed, never-medicated PD.
- Excess grip force was present before any medication, so it is a disease feature, not a drug effect.
- Confidence: medium. Abstract only.

**A1.25 [Jordan 1994]** Jordan N, Sagar HJ. The role of the striatum in motor learning: dissociations between isometric motor control processes in Parkinson's disease. Int J Neurosci. 1994;77(3-4):153-165. PMID 7814209. DOI 10.3109/00207459408986027.
- Early non-demented PD. Isometric task without visual feedback, with and without dopamine replacement.
- PD undershot the target disproportionately yet learned normally; treatment did not change task performance despite clinical gains.
- Confidence: medium. Abstract only.

**A1.26 [Jo 2016]** Jo HJ, Ambike S, Lewis MM, Huang X, Latash ML. Finger force changes in the absence of visual feedback in patients with Parkinson's disease. Clin Neurophysiol. 2016;127(1):684-692. PMID 26072437. DOI 10.1016/j.clinph.2015.05.023. PMC4669237.
- PD vs controls. Two-finger constant force without vision.
- Force fell exponentially in both groups but faster in PD; drift in force sharing between fingers did not differ.
- Confidence: medium. Abstract only. Agrees with [Vaillancourt 2001a] from a different lab.

### A2. Medication, sequence effect and severity

**A2.1 [Park 2014]** Park J, Lewis MM, Huang X, Latash ML. Dopaminergic modulation of motor coordinaton in Parkinson's disease. Parkinsonism Relat Disord. 2014;20(1):64-68. PMID 24090949. DOI 10.1016/j.parkreldis.2013.09.019. PMC3946854. (Title spelling as published.)
- 8 early PD tested OFF then ON.
- OFF, finger strength was about 10 to 12% lower than ON. ON brought stronger synergies, earlier anticipatory adjustments, time to peak in quick pulses about 40 ms shorter (0.18 vs 0.22 s). The enslaving index did not change (about 0.07 to 0.09 per finger in both states, from regressions of each finger's force on total force during a 12 s ramp to 40% MVC).
- Confidence: high. Full text read (methods and Table 2).

**A2.2 [Johnson 1996]** Johnson MT, Kipnis AN, Coltz JD, Gupta A, Silverstein P, Zwiebel F, et al. Effects of levodopa and viscosity on the velocity and accuracy of visually guided tracking in Parkinson's disease. Brain. 1996;119(3):801-813. PMID 8673492. DOI 10.1093/brain/119.3.801.
- PD vs controls. Wrist tracking of sine and step targets, OFF and ON, with viscous loads.
- Levodopa raised tracking velocity, but tracking error stayed above controls and did not change with levodopa: a drug-responsive speed deficit next to a drug-resistant error-correction deficit.
- Confidence: medium. Abstract only.

**A2.3 [Fischer 2019]** Fischer P, Pogosyan A, Green AL, Aziz TZ, Hyam J, Foltynie T, et al. Beta synchrony in the cortico-basal ganglia network during regulation of force control on and off dopamine. Neurobiol Dis. 2019;127:253-263. PMID 30849510. DOI 10.1016/j.nbd.2019.03.004. PMC6517271.
- 18 PD with DBS electrodes (11 STN, 7 GPi), ON and OFF. Visually guided force matching with a pen on a force tablet.
- ON, peak rate of force change was faster. Basal ganglia beta power dropped during both increases and decreases of force, and high beta went with slower adjustments.
- Confidence: medium. Abstract only.

**A2.4 [Stewart 2009]** Stewart KC, Fernandez HH, Okun MS, Alberts JL, Malaty IA, Rodriguez RL, et al. Effects of dopaminergic medication on objective tasks of deftness, bradykinesia and force control. J Neurol. 2009;256(12):2030-2035. PMID 19597692. DOI 10.1007/s00415-009-5235-y.
- 11 PD with motor fluctuations vs 10 controls, OFF and ON.
- Dexterity and bradykinesia improved ON, but the finger-thumb force control tasks showed no PD vs control difference.
- Confidence: medium. Abstract only. A negative result.

**A2.5 [Wenzelburger 2002]** Wenzelburger R, Zhang BR, Pohle S, Klebe S, Lorenz D, Herzog J, et al. Force overflow and levodopa-induced dyskinesias in Parkinson's disease. Brain. 2002;125(4):871-879. PMID 11912119. DOI 10.1093/brain/awf084.
- 23 PD with dyskinesia, 10 without, plus controls. Grip-lift ON and OFF.
- Only patients with dyskinesia overshot grip force when ON (peak grip about 51% above OFF). Force excess tracked dyskinesia severity (r = 0.79), not motor score.
- Confidence: medium. Abstract only.

**A2.6 [Kang 2010]** Kang SY, Wasaka T, Shamim EA, Auh S, Ueki Y, Lopez GJ, et al. Characteristics of the sequence effect in Parkinson's disease. Mov Disord. 2010;25(13):2148-2155. PMID 20669182. DOI 10.1002/mds.23251. PMC4782591.
- 11 advanced PD. Placebo-controlled four-way crossover (levodopa, rTMS). Computer-based pegboard.
- Levodopa and rTMS each improved general slowness; neither reduced the progressive slowing across repetitions (sequence effect), which was unrelated to clinical fatigue.
- Confidence: medium. Abstract only.

**A2.7 [Tinaz 2016]** Tinaz S, Pillai AS, Hallett M. Sequence Effect in Parkinson's Disease Is Related to Motor Energetic Cost. Front Neurol. 2016;7:83. PMID 27252678. DOI 10.3389/fneur.2016.00083. PMC4877367.
- 12 PD (OFF then ON) vs 12 controls. Repeated grip squeezes to 50% MVC paced at 1.25 Hz for 90 s, with and without visual feedback. Decrement = slope of peak force over the first 20 squeezes (about 15 s).
- Visual feedback flattened the decrement in every group. PD ON without feedback declined more steeply than controls. PD spent more total force-time (summed impulse) regardless of medication. Decrement did not correlate with UPDRS.
- Confidence: high. Full text read.

**A2.8 [Espay 2011]** Espay AJ, Giuffrida JP, Chen R, Payne M, Mazzella F, Dunn E, et al. Differential response of speed, amplitude, and rhythm to dopaminergic medications in Parkinson's disease. Mov Disord. 2011;26(14):2504-2508. PMID 21953789. DOI 10.1002/mds.23893. PMC3318914.
- 85 PD, OFF and ON, motion sensors on the most affected hand during UPDRS hand tasks.
- Reduced amplitude was more common than slowness, yet medication mainly improved speed; the decline within a bout was not improved.
- Confidence: medium. Abstract only.

**A2.9 [Bologna 2020]** Bologna M, Paparella G, Fasano A, Hallett M, Berardelli A. Evolving concepts on bradykinesia. Brain. 2020;143(3):727-750. PMID 31834375. DOI 10.1093/brain/awz344. PMC8205506.
- Narrative review.
- In PD, bradykinesia is slowness plus small amplitude plus the sequence effect. Levodopa helps these unevenly and does not clearly change the sequence effect. Basal ganglia, motor cortex, cerebellum and sensory processing all contribute.
- Confidence: high for this summary. Abstract read.

**A2.10 [Goetz 2008]** Goetz CG, Tilley BC, Shaftman SR, Stebbins GT, Fahn S, Martinez-Martin P, et al. Movement Disorder Society-sponsored revision of the Unified Parkinson's Disease Rating Scale (MDS-UPDRS): scale presentation and clinimetric testing results. Mov Disord. 2008;23(15):2129-2170. PMID 19025984. DOI 10.1002/mds.22340.
- Clinimetric study, 877 PD.
- Four parts, Part III is the motor examination. Internal consistency 0.79 to 0.93; part scores preferred over one grand total. Any PD study of Force Pilot would correlate its measures with Part III.
- Confidence: high. Abstract read.

### A3. Mechanism papers used for the rationale

**A3.1 [Prodoehl 2009]** Prodoehl J, Corcos DM, Vaillancourt DE. Basal ganglia mechanisms underlying precision grip force control. Neurosci Biobehav Rev. 2009;33(6):900-908. PMID 19428499. DOI 10.1016/j.neubiorev.2009.03.004. PMC2684813.
- Review. Specific basal ganglia nuclei set parameters of precision grip force, which is why grip force tasks are sensitive to PD.
- Confidence: medium. Abstract read.

**A3.2 [Vaillancourt 2007]** Vaillancourt DE, Yu H, Mayka MA, Corcos DM. Role of the basal ganglia and frontal cortex in selecting and producing internally guided force pulses. NeuroImage. 2007;36(3):793-803. PMID 17451971. DOI 10.1016/j.neuroimage.2007.03.002. PMC1950146.
- Healthy fMRI. GPi, STN and posterior putamen were more active for repeated pulses than for a steady hold; the caudate was engaged when choosing between pulse sizes. Cited in force_pilot.py for the Heartbeat level.
- Confidence: medium. Abstract read.

**A3.3 [Spraker 2009]** Spraker MB, Corcos DM, Vaillancourt DE. Cortical and subcortical mechanisms for precisely controlled force generation and force relaxation. Cereb Cortex. 2009;19(11):2640-2650. PMID 19254959. DOI 10.1093/cercor/bhp015. PMC2758679.
- Healthy fMRI. Slow controlled release used more right dorsolateral prefrontal cortex; generation used more motor cortex and caudate. Release is not generation in reverse.
- Confidence: medium. Abstract read.

**A3.4 [Spraker 2010]** Spraker MB, Prodoehl J, Corcos DM, Comella CL, Vaillancourt DE. Basal ganglia hypoactivity during grip force in drug naïve Parkinson's disease. Hum Brain Mapp. 2010;31(12):1928-1941. PMID 20225221. DOI 10.1002/hbm.20987. PMC6870615.
- 14 drug-naive early PD vs 14 controls, fMRI during 2 s and 4 s grip pulse tasks.
- The task with more switching between contraction and relaxation showed under-activity across all basal ganglia nuclei, M1 and SMA, and it grew as the task went on.
- Confidence: medium. Abstract read.

**A3.5 [Redgrave 2010]** Redgrave P, Rodriguez M, Smith Y, Rodriguez-Oroz MC, Lehericy S, Bergman H, et al. Goal-directed and habitual control in the basal ganglia: implications for Parkinson's disease. Nat Rev Neurosci. 2010;11(11):760-772. PMID 20944662. DOI 10.1038/nrn2915. PMC3124757.
- Review. Dopamine loss is greatest in the posterior putamen (habitual control), so people with PD lean on goal-directed control. The usual explanation for why explicit external goals and cues help.
- Confidence: medium. Abstract read.

**A3.6 [Jahanshahi 1995]** Jahanshahi M, Jenkins IH, Brown RG, Marsden CD, Passingham RE, Brooks DJ. Self-initiated versus externally triggered movements. I. An investigation using measurement of regional cerebral blood flow with PET and movement-related potentials in normal and Parkinson's disease subjects. Brain. 1995;118(4):913-933. PMID 7655888. DOI 10.1093/brain/118.4.913.
- 6 PD OFF vs 6 controls. PET and movement-related potentials during self-initiated vs externally triggered finger extension.
- Self-initiated movements showed smaller early potentials and SMA under-activation in PD; externally triggered movements showed no group difference.
- Confidence: medium. Abstract read.

### A4. Visual feedback, prediction, cueing and motor learning in PD

**A4.1 [Flowers 1976]** Flowers KA. Visual "closed-loop" and "open-loop" characteristics of voluntary movement in patients with Parkinsonism and intention tremor. Brain. 1976;99(2):269-310. PMID 990899. DOI 10.1093/brain/99.2.269.
- PD vs controls vs intention tremor. Joystick target acquisition.
- PD moved at one slow rate for every distance, as if steering under vision the whole way; hiding the target or cursor changed their movements; practice on a fixed sequence did not help.
- Confidence: medium. Abstract read.

**A4.2 [Cooke 1978]** Cooke JD, Brown JD, Brooks VB. Increased dependence on visual information for movement control in patients with Parkinson's disease. Can J Neurol Sci. 1978;5(4):413-415. PMID 743651. DOI 10.1017/s0317167100024197.
- PD elbow movements with and without the target displayed.
- Without the target, PD drifted and ended with position errors far above normal sensing limits.
- Confidence: medium. Abstract read; short report, sample size not in abstract.

**A4.3 [Day 1984]** Day BL, Dick JP, Marsden CD. Patients with Parkinson's disease can employ a predictive motor strategy. J Neurol Neurosurg Psychiatry. 1984;47(12):1299-1306. PMID 6512550. DOI 10.1136/jnnp.47.12.1299. PMC1028137.
- 12 PD vs 8 controls (elbow tracking), then 5 vs 5 (wrist, ON and OFF).
- Both groups cut error and lag on repeated patterns, with lag below 20 ms even in OFF patients; PD gained less error reduction.
- Confidence: medium. Abstract read (full text is a scan).

**A4.4 [Bloxham 1984]** Bloxham CA, Mindel TA, Frith CD. Initiation and execution of predictable and unpredictable movements in Parkinson's disease. Brain. 1984;107(2):371-384. PMID 6722509. DOI 10.1093/brain/107.2.371.
- 9 PD vs age-matched controls.
- No group difference in tracking; both removed lag on predictable targets. PD could not use advance information to shorten reaction time.
- Confidence: medium. Abstract read.

**A4.5 [Frith 1986]** Frith CD, Bloxham CA, Carpenter KN. Impairments in the learning and performance of a new manual skill in patients with Parkinson's disease. J Neurol Neurosurg Psychiatry. 1986;49(6):661-668. PMID 3734823. DOI 10.1136/jnnp.49.6.661. PMC1028849.
- 12 PD. Joystick tracking of a semi-predictable target and a mirror-reversed task, two 3 min sessions.
- PD performed worse but learned, especially after a rest. They lacked the quick gain controls showed in the first minute of each session.
- Confidence: medium. Abstract read.

**A4.6 [Soliveri 1992]** Soliveri P, Brown RG, Jahanshahi M, Marsden CD. Effect of practice on performance of a skilled motor task in patients with Parkinson's disease. J Neurol Neurosurg Psychiatry. 1992;55(6):454-460. PMID 1619411. DOI 10.1136/jnnp.55.6.454. PMC1014900.
- PD vs controls, buttoning with and without foot tapping.
- PD improved with practice but needed more of it to match controls.
- Confidence: medium. Abstract read.

**A4.7 [Verschueren 1997]** Verschueren SM, Swinnen SP, Dom R, De Weerdt W. Interlimb coordination in patients with Parkinson's disease: motor learning deficits and the importance of augmented information feedback. Exp Brain Res. 1997;113(3):497-508. PMID 9108216. DOI 10.1007/pl00005602.
- PD vs older controls learning a new bimanual pattern with real-time augmented visual feedback.
- Both improved with feedback; with it withdrawn PD lost more and drifted back to easy patterns. Learning stayed tied to the feedback.
- Confidence: medium. Abstract read.

**A4.8 [Guadagnoli 2002]** Guadagnoli MA, Leis B, Van Gemmert AW, Stelmach GE. The relationship between knowledge of results and motor learning in Parkinsonian patients. Parkinsonism Relat Disord. 2002;9(2):89-95. PMID 12473398. DOI 10.1016/s1353-8020(02)00007-x.
- PD vs controls. Timing task with feedback after every trial or every fifth trial.
- Controls retained best with less frequent feedback; PD retained best with feedback on every trial.
- Confidence: medium. Abstract read.

**A4.9 [Chiviacowsky 2012]** Chiviacowsky S, Wulf G, Lewthwaite R, Campos T. Motor learning benefits of self-controlled practice in persons with Parkinson's disease. Gait Posture. 2012;35(4):601-605. PMID 22209649. DOI 10.1016/j.gaitpost.2011.12.003.
- Randomised, 28 PD. Balance task; one group chose when to use an assist, the other was yoked.
- Choice improved next-day retention and motivation. Balance, not hand.
- Confidence: medium. Abstract read.

**A4.10 [Nieuwboer 2009]** Nieuwboer A, Rochester L, Müncks L, Swinnen SP. Motor learning in Parkinson's disease: limitations and potential for rehabilitation. Parkinsonism Relat Disord. 2009;15 Suppl 3:S53-S58. PMID 20083008. DOI 10.1016/S1353-8020(09)70781-3.
- Review. Acquisition and retention are relatively preserved but slower and less efficient; cues and extra sensory information help performance; some gains stay tied to the cue.
- Confidence: medium. Abstract read.

**A4.11 [Marinelli 2017]** Marinelli L, Quartarone A, Hallett M, Frazzitta G, Ghilardi MF. The many facets of motor learning and their relevance for Parkinson's disease. Clin Neurophysiol. 2017;128(7):1127-1141. PMID 28511125. DOI 10.1016/j.clinph.2017.03.042. PMC5486221.
- Review. Learning that relies on attention and strategy is most affected; levodopa does not reverse the learning deficit; retention of newly learned skills is often reduced, even early in the disease.
- Confidence: medium. Abstract read.

**A4.12 [Felix 2012]** Felix K, Gain K, Paiva E, Whitney K, Jenkins ME, Spaulding SJ. Upper Extremity Motor Learning among Individuals with Parkinson's Disease: A Meta-Analysis Evaluating Movement Time in Simple Tasks. Parkinsons Dis. 2012;2012:589152. PMID 22191071. DOI 10.1155/2012/589152. PMC3236460.
- Meta-analysis of upper-limb reaching practice.
- PD and controls both became faster with practice; controls improved more.
- Confidence: medium. Abstract read; pooled values not given in the abstract.

**A4.13 [Cristini 2023]** Cristini J, Parwanta Z, De Las Heras B, Medina-Rincon A, Paquette C, Doyon J, et al. Motor Memory Consolidation Deficits in Parkinson's Disease: A Systematic Review with Meta-Analysis. J Parkinsons Dis. 2023;13(6):865-892. PMID 37458048. DOI 10.3233/JPD-230038. PMC10578244.
- Systematic review and meta-analysis, 46 studies.
- PD retained less overall (SMD -0.17), mainly in sensorimotor (-0.31) and visuomotor adaptation (-1.55) tasks, not sequential fine motor tasks (+0.17, not significant). Deficits were no longer significant when augmented feedback was given during practice.
- Confidence: high. Abstract read.

**A4.14 [Spaulding 2013]** Spaulding SJ, Barber B, Colby M, Cormack B, Mick T, Jenkins ME. Cueing and gait improvement among people with Parkinson's disease: a meta-analysis. Arch Phys Med Rehabil. 2013;94(3):562-570. PMID 23127307. DOI 10.1016/j.apmr.2012.10.026.
- Meta-analysis of 25 gait cueing studies.
- Auditory cues improved cadence, stride length and speed (Hedges g 0.50 to 0.56); visual cues improved stride length only (g 0.55). Cueing evidence is mostly gait, not hand.
- Confidence: medium. Abstract read.

**A4.15 [Nackaerts 2016a]** Nackaerts E, Heremans E, Vervoort G, Smits-Engelsman BC, Swinnen SP, Vandenberghe W, et al. Relearning of Writing Skills in Parkinson's Disease After Intensive Amplitude Training. Mov Disord. 2016;31(8):1209-1216. PMID 26990651. DOI 10.1002/mds.26565.
- Placebo-controlled RCT, 38 PD. 30 min a day, 5 days a week for 6 weeks: writing-size training on a tablet with target zones vs stretching.
- Writing size and its consistency improved (effects 7 to 17%), transferred to untrained sequences, dual-task writing and daily writing, and held after 6 weeks.
- Confidence: medium. Abstract read. The closest PD RCT to fine motor practice against a visual target.

**A4.16 [Nackaerts 2016b]** Nackaerts E, Nieuwboer A, Broeder S, Smits-Engelsman BC, Swinnen SP, Vandenberghe W, et al. Opposite Effects of Visual Cueing During Writing-Like Movements of Different Amplitudes in Parkinson's Disease. Neurorehabil Neural Repair. 2016;30(5):431-439. PMID 26276122. DOI 10.1177/1545968315601361.
- 15 PD vs 15 controls. Loops between target lines 1.0 cm or 0.6 cm apart.
- 1.0 cm lines improved size, consistency and speed; 0.6 cm lines made writing smaller in both groups. Tight visual targets add an accuracy demand that can shrink movement.
- Confidence: medium. Abstract read.

### A5. Interventions: fine motor training, games and technology in PD

**A5.1 [Proud 2024]** Proud EL, Miller KJ, Morris ME, McGinley JL, Blennerhassett JM. Effects of Upper Limb Exercise or Training on Hand Dexterity and Function in People With Parkinson Disease: A Systematic Review and Meta-analysis. Arch Phys Med Rehabil. 2024;105(7):1375-1387. PMID 38042246. DOI 10.1016/j.apmr.2023.11.009.
- 18 RCTs (n = 704), GRADE rated.
- Moderate-quality evidence of a small dexterity gain (SMD 0.26, 95% CI 0.07 to 0.44). Self-reported hand function unclear; handwriting evidence low quality. Best dose and active ingredients unknown.
- Confidence: high. Abstract read. The best single anchor for "hand training helps PD a little".

**A5.2 [Malwanage 2024]** Malwanage KT, Dissanayaka TD, Allen NE, Paul SS. Effect of Proprioceptive Training Compared With Other Interventions for Upper Limb Deficits in People With Parkinson Disease: A Systematic Review and Meta-analysis of Randomized Controlled Trials. Arch Phys Med Rehabil. 2024;105(7):1364-1374. PMID 37951376. DOI 10.1016/j.apmr.2023.10.016.
- 8 RCTs (n = 344).
- Very low certainty that proprioceptive training improves fine dexterity (SMD 0.34 to 0.36) and dominant-hand gross dexterity; no effect on arm function or quality of life.
- Confidence: medium. Abstract read.

**A5.3 [Allen 2017]** Allen NE, Song J, Paul SS, Smith S, O'Duffy J, Schmidt M, et al. An interactive videogame for arm and hand exercise in people with Parkinson's disease: A randomized controlled trial. Parkinsonism Relat Disord. 2017;41:66-72. PMID 28528804. DOI 10.1016/j.parkreldis.2017.05.011.
- RCT, 38 PD (19 per arm), Sydney. Tablet exergames at home, 3 times a week for 12 weeks.
- No gain on the nine hole peg test or most secondary outcomes; tapping became faster but less accurate. Games were enjoyed and safe. The authors suggest the games pushed speed at the cost of accuracy and call for task-specific game design.
- Confidence: high. Abstract read.

**A5.4 [Heinzle 2026]** Heinzle K, Habig J, Pröglhöf M, Diwald A, Mildner S, Haslinger M, et al. Immersive virtual reality upper-limb exercises in people with Parkinson's disease: an observer-blinded randomised controlled trial. J Neuroeng Rehabil. 2026;23(1):9. PMID 41508050. DOI 10.1186/s12984-025-01851-1. PMC12781375.
- Observer-blinded RCT, 58 PD inpatients. 30 min, 4 times a week for 4 weeks, VR vs conventional upper-limb training.
- Both groups improved. No group by time differences on arm function; hand function improved only with conventional training (small between-group effect). Adherence high, usability good (SUS 72.5).
- Confidence: high. Abstract read.

**A5.5 [Vanbellingen 2017]** Vanbellingen T, Nyffeler T, Nigg J, Janssens J, Hoppe J, Nef T, et al. Home based training for dexterity in Parkinson's disease: A randomized controlled trial. Parkinsonism Relat Disord. 2017;41:92-98. PMID 28578819. DOI 10.1016/j.parkreldis.2017.05.021.
- Single-blind RCT, 103 PD. 4 weeks, 5 times a week, dexterity program vs Thera-band.
- The dexterity program beat control on the nine hole peg test and dexterity-related daily activities after training, but not at 12-week follow-up.
- Confidence: high. Abstract read.

**A5.6 [Cetin 2024]** Çetin B, Kılınç M, Çakmaklı GY. The effects of exergames on upper extremity performance, trunk mobility, gait, balance, and cognition in Parkinson's disease: a randomized controlled study. Acta Neurol Belg. 2024;124(3):853-863. PMID 38182919. DOI 10.1007/s13760-023-02451-3.
- RCT, 23 randomised, 20 analysed, 24 supervised sessions.
- Both groups improved; the exergame group improved more on dominant-hand nine hole peg test, one dexterity subtest and cognition.
- Confidence: medium. Abstract read; small.

**A5.7 [van Beek 2019]** van Beek JJW, van Wegen EEH, Bohlhalter S, Vanbellingen T. Exergaming-Based Dexterity Training in Persons With Parkinson Disease: A Pilot Feasibility Study. J Neurol Phys Ther. 2019;43(3):168-174. PMID 31136450. DOI 10.1097/NPT.0000000000000278.
- Single-group pilot, 10 PD, 4 weeks.
- Adherence 99%, motivation rose, usability acceptable to very good; people with impaired dexterity improved on the peg test.
- Confidence: medium. Abstract read; uncontrolled.

**A5.8 [Dockx 2016]** Dockx K, Bekkers EM, Van den Bergh V, Ginis P, Rochester L, Hausdorff JM, et al. Virtual reality for rehabilitation in Parkinson's disease. Cochrane Database Syst Rev. 2016;12:CD010760. PMID 28000926. DOI 10.1002/14651858.CD010760.pub2. PMC6463967.
- Cochrane review, 8 trials, 263 PD.
- Low-quality evidence that VR may lengthen steps and strides against physiotherapy (SMD 0.69) and is otherwise similar; no adverse events. Mostly gait and balance.
- Confidence: high. Abstract read.

**A5.9 [Garcia-Agundez 2019]** Garcia-Agundez A, Folkerts AK, Konrad R, Caserman P, Tregel T, Goosses M, et al. Recent advances in rehabilitation for Parkinson's Disease with Exergames: A Systematic Review. J Neuroeng Rehabil. 2019;16(1):17. PMID 30696453. DOI 10.1186/s12984-019-0492-1. PMC6352377.
- Systematic review, 64 publications from 2014.
- Exergames look feasible, safe and at least as good as usual rehabilitation in the trials found. The review asks for game parameters to be linked to clinical scores such as UPDRS, and for task specificity.
- Confidence: medium. Abstract read.

**A5.10 [Lahude 2023]** Lahude AB, Souza Corrêa P, P Cabeleira ME, Cechetti F. The impact of virtual reality on manual dexterity of Parkinson's disease subjects: a systematic review. Disabil Rehabil Assist Technol. 2023;18(7):1237-1244. PMID 35077662. DOI 10.1080/17483107.2021.2001060.
- Systematic review, 8 studies with dexterity outcomes.
- Most reported dexterity gains, but most had high risk of bias and very mixed protocols.
- Confidence: medium. Abstract read.

**A5.11 [Fernandez-Gonzalez 2023]** Fernández-González D, Rodriguez-Costa I, Sanz-Esteban I, Estrada-Barranco C. Therapeutic intervention with virtual reality in patients with Parkinson's disease for upper limb motor training: A systematic review. Rehabilitacion (Madr). 2023;57(2):100751. PMID 36344299. DOI 10.1016/j.rh.2022.06.003.
- Systematic review, 7 RCTs.
- Reports positive upper-limb effects, but the abstract gives no pooled effect or bias grading. Weak.
- Confidence: low to medium. Abstract read.

**A5.12 [Tao 2024]** Tao Y, Luo J, Tian J, Peng S, Wang H, Cao J, et al. The role of robot-assisted training on rehabilitation outcomes in Parkinson's disease: a systematic review and meta-analysis. Disabil Rehabil. 2024;46(18):4049-4067. PMID 37818694. DOI 10.1080/09638288.2023.2266178.
- 21 studies (787 participants), only 3 on the upper limb.
- Robotics helped gait, balance and fatigue; upper-limb outcomes (Purdue, Box and Block) showed no significant effect.
- Confidence: medium. Abstract read.

**A5.13 [Goncalves 2021]** Gonçalves HR, Rodrigues AM, Santos CP. Vibrotactile biofeedback devices in Parkinson's disease: a narrative review. Med Biol Eng Comput. 2021;59(6):1185-1199. PMID 33969461. DOI 10.1007/s11517-021-02365-3.
- Narrative review.
- Vibrotactile feedback in PD has been built mainly for gait (freezing, balance, falls) and shows promise, but clinical evidence is thin. Nothing on fingertip error feedback of the kind Force Pilot's corridor-exit buzz gives.
- Confidence: medium. Abstract read.

**A5.14 [Petzinger 2013]** Petzinger GM, Fisher BE, McEwen S, Beeler JA, Walsh JP, Jakowec MW. Exercise-enhanced neuroplasticity targeting motor and cognitive circuitry in Parkinson's disease. Lancet Neurol. 2013;12(7):716-726. PMID 23769598. DOI 10.1016/S1474-4422(13)70123-6. PMC3690528.
- Review. Goal-based skill training with instruction and feedback, plus aerobic exercise, may improve motor control in mild to moderate PD through experience-dependent plasticity; animal work supports the mechanism.
- Confidence: medium. Abstract read. General rationale only.

### A6. Force-feedback training anchors outside PD (cited in force_pilot.py or needed to frame Force Pilot as training)

**A6.1 [Taud 2021]** Taud B, Lindenberg R, Darkow R, Wevers J, Höfflin D, Grittner U, et al. Limited Add-On Effects of Unilateral and Bilateral Transcranial Direct Current Stimulation on Visuo-Motor Grip Force Tracking Task Training Outcome in Chronic Stroke. A Randomized Controlled Trial. Front Neurol. 2021;12:736075. PMID 34858310. DOI 10.3389/fneur.2021.736075. PMC8631774.
- Double-blind RCT, 40 chronic stroke. Every arm had 5 days of grip force tracking training; the randomised factor was tDCS (anodal, dual or sham).
- Trained-task performance improved in all arms. Anodal tDCS added about 2.6 to 2.8 Fugl-Meyer points over sham; no arm improved the Wolf Motor Function Test.
- Confidence: high. Abstract read. See E4: this trial cannot show that tracking training itself drives recovery.

**A6.2 [Seo 2025]** Seo NJ, Schranz C, Coupland K, Blaschke J, Scronce G, Finetto C, et al. Biofeedback Training for 3-Dimensional Finger Force Control to Improve Upper Limb Function Poststroke: An RCT. Stroke. 2025;56(8):2266-2276. PMID 40401398. DOI 10.1161/STROKEAHA.125.050965. PMC12303752.
- Double-blind RCT, 45 stroke survivors, 18 sessions of fingertip force training with 3D vs 1D visual feedback.
- 3D feedback gave larger ARAT gains (3.5 vs 0.8 points), held at 1 month. Both arms trained force, so the result is about what the feedback shows, not whether force training works.
- Confidence: high. Abstract read.

**A6.3 [Kurillo 2005]** Kurillo G, Gregoric M, Goljar N, Bajd T. Grip force tracking system for assessment and rehabilitation of hand function. Technol Health Care. 2005;13(3):137-149. PMID 15990417 (no DOI in PubMed).
- 32 healthy across ages; 10 stroke trained without a control group.
- Tracking separated age groups; 8 of 10 stroke patients improved tracking. Authors confirmed.
- Confidence: medium. Abstract read.

**A6.4 [Naik 2011]** Naik SK, Patten C, Lodha N, Coombes SA, Cauraugh JH. Force control deficits in chronic stroke: grip formation and release phases. Exp Brain Res. 2011;211(1):1-15. PMID 21448576. DOI 10.1007/s00221-011-2637-8.
- 9 stroke, 9 age-matched, 9 young. Grip ramps at 5, 10, 20% of max per second, hold, release.
- Step number and mean pause duration separated groups better than RMSE; stroke showed the largest deficits in release. This is stroke evidence, not PD or ageing.
- Confidence: medium. Abstract read.

**A6.5 [Archer 2018]** Archer DB, Kang N, Misra G, Marble S, Patten C, Coombes SA. Visual feedback alters force control and functional activity in the visuomotor network after stroke. NeuroImage Clin. 2018;17:505-517 (online 2017). PMID 29201639. DOI 10.1016/j.nicl.2017.11.012. PMC5700823.
- 15 chronic stroke vs 15 controls. Grip at 15% MVC under low, medium and high visual gain, where cursor = target + gain × error (the same rule Force Pilot uses).
- Error fell with gain in both groups; the stroke minus control gap was about 21% MVC at low gain, 6% at medium and 3% at high.
- Confidence: high. Full text read; the numbers in force-control.md are correct.

**A6.6 [Lodha 2013]** Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH. Increased force variability in chronic stroke: contributions of force modulation below 1 Hz. PLoS One. 2013;8(12):e83468. PMID 24386208. DOI 10.1371/journal.pone.0083468. PMC3873339.
- 13 stroke vs 13 controls, grip holds.
- Stroke hands had more power near 0.2 Hz and less near 0.6 Hz; the sub-1 Hz profile predicted variability (R² = 0.80). No PD data, so the notebook's Lodha bands are exploratory for PD.
- Confidence: high. Abstract read.

**A6.7 [Keogh 2019]** Keogh JWL, O'Reilly S, O'Brien E, Morrison S, Kavanagh JJ. Can Resistance Training Improve Upper Limb Postural Tremor, Force Steadiness and Dexterity in Older Adults? A Systematic Review. Sports Med. 2019;49(8):1199-1216. PMID 31236903. DOI 10.1007/s40279-019-01141-6.
- Systematic review, 14 studies.
- All 8 studies in healthy older adults reported less tremor or better steadiness or dexterity; results in clinical groups were mixed (small or no change in osteoarthritis and stroke). The abstract names COPD, essential tremor, osteoarthritis and stroke and does not mention PD. Authors now confirmed.
- Confidence: medium. Abstract read.

### A7. Healthy-adult reference values and methods

**A7.1 [Moritz 2005]** Moritz CT, Barry BK, Pascoe MA, Enoka RM. Discharge rate variability influences the variation in force fluctuations across the working range of a hand muscle. J Neurophysiol. 2005;93(5):2449-2459. PMID 15615827. DOI 10.1152/jn.01122.2004.
- Young adults, index finger abduction, 2 to 95% MVC.
- CV of force fell from 4.9% at 2% MVC to 1.4% at 15% MVC and stayed at 1.2 to 1.9% above that.
- Confidence: high for these values. Abstract read.

**A7.2 [Tracy 2015]** Tracy BL, Hitchcock LN, Welsh SJ, Paxton RJ, Feldman-Kothe CE. Front Aging Neurosci. 2015;7:229. PMID 26696881. DOI 10.3389/fnagi.2015.00229. PMC4678381. (Full title on PubMed; not repeated because it contains a word this document's style rules exclude.)
- 27 young vs 14 older. Index abduction at 2.5, 30, 65% MVC, vision on and off.
- Young CV with vs without vision: 4.8 vs 4.3% (2.5% MVC), 3.2 vs 3.2% (30%), 3.5 vs 4.2% (65%). Older adults were less steady with vision at 2.5% MVC (6.6 vs 4.2%).
- Confidence: high. Abstract read. Confirms the movement-disorders.md entry and gives its authors.

**A7.3 [Slifkin 2000]** Slifkin AB, Vaillancourt DE, Newell KM. Intermittency in the control of continuous force production. J Neurophysiol. 2000;84(4):1708-1718. PMID 11024063. DOI 10.1152/jn.2000.84.4.1708.
- Adults holding force with feedback updated from 0.2 to 25.6 Hz.
- Performance levelled off near 6.4 Hz updates (about 150 ms of visual integration), while corrections appeared as force oscillations near 1 Hz.
- Confidence: high. Abstract read.

**A7.4 [Miall 1993]** Miall RC, Weir DJ, Stein JF. Intermittency in human manual tracking tasks. J Mot Behav. 1993;25(1):53-63. PMID 12730041. DOI 10.1080/00222895.1993.9941639.
- Healthy joystick tracking.
- Tracking acts like an intermittent controller with a small error deadzone; at higher speeds starting errors fit a refractory delay of about 170 ms.
- Confidence: medium. Abstract read.

**A7.5 [Cathers 1996]** Cathers I, O'Dwyer N, Neilson P. Tracking performance with sinusoidal and irregular targets under different conditions of peripheral feedback. Exp Brain Res. 1996;111(3):437-446. PMID 8911938. DOI 10.1007/BF00228733.
- Healthy forearm tracking.
- Sinusoids can be followed much faster than irregular signals because the rhythm can be generated internally and synchronised; the usual visual tracking ceiling is about 2 Hz.
- Confidence: medium. Abstract read.

**A7.6 [Baweja 2010]** Baweja HS, Kennedy DM, Vu J, Vaillancourt DE, Christou EA. Greater amount of visual feedback decreases force variability by reducing force oscillations from 0-1 and 3-7 Hz. Eur J Appl Physiol. 2010;108(5):935-943. PMID 19953262. DOI 10.1007/s00421-009-1301-5. PMC2863099.
- 14 young. Index abduction at 2 and 10% MVC across 13 visual gains.
- Force SD fell from 0.09 ± 0.04 N at low gain to 0.06 ± 0.02 N at moderate to high gain, through about 50% less power at 0 to 1 Hz and about 20% less at 3 to 7 Hz.
- Confidence: high. Abstract read. Gives authors for the unattributed force-control.md entry.

**A7.7 [Fox 2013]** Fox EJ, Baweja HS, Kim C, Kennedy DM, Vaillancourt DE, Christou EA. Modulation of force below 1 Hz: age-associated differences and the effect of magnified visual feedback. PLoS One. 2013;8(2):e55970. PMID 23409099. DOI 10.1371/journal.pone.0055970. PMC3569433.
- 10 young vs 10 older. 2% MVC index abduction with visual angle varied or removed.
- Magnified feedback shifted sub-1 Hz power; older adults became more variable with magnification; the sub-1 Hz shifts predicted the variability change (R² = 0.80).
- Confidence: high. Abstract read. This is the PMC3569433 entry in force-control.md.

**A7.8 [Camacho-Villa 2025]** Camacho-Villa MA, Giráldez-García MA, Sevilla-Sanchez M, Rivera-Mejía SL, Carballeira E. Relationship Between Force Steadiness and Functionality in Older Adults: A Systematic Review With Meta-Analysis. Scand J Med Sci Sports. 2025;35(4):e70040. PMID 40176413. DOI 10.1111/sms.70040. PMC12881927.
- 21 studies, 15 pooled.
- Upper-limb steadiness correlated with task performance at r = 0.58 (95% CI 0.49 to 0.65), with moderate to high risk of bias and signs of publication bias.
- Confidence: high. Abstract read. Year 2025 confirmed.

**A7.9 [Blomkvist 2018]** Blomkvist AW, Eika F, de Bruin ED, Andersen S, Jorgensen M. Handgrip force steadiness in young and older adults: a reproducibility study. BMC Musculoskelet Disord. 2018;19(1):96. PMID 29609577. DOI 10.1186/s12891-018-2015-9. PMC5879800.
- 10 young and 30 older adults. Handgrip at 5, 10, 25% MVC on a Wii Balance Board, 7 days apart.
- Everyone improved at the second session. CV measures reproduced well (average ICC about 0.81); area between force and target reproduced poorly (0.46). Young were steadier than old.
- Confidence: high. Abstract read. Authors now confirmed.

**A7.10 [Carey 1988]** Carey JR, Patterson R, Hollenstein PJ. Sensitivity and reliability of force tracking and joint-movement tracking scores in healthy subjects. Phys Ther. 1988;68(7):1087-1091. PMID 3290913. DOI 10.1093/ptj/68.7.1087.
- 14 healthy adults, handgrip force tracking, retested after 20 min.
- Accuracy improved from pre to post test (a practice effect) and ICCs were acceptable. The closest precedent for Force Pilot's pass 1 vs pass 2 design.
- Confidence: medium. Abstract read.

**A7.11 [Bellumori 2011]** Bellumori M, Jaric S, Knight CA. The rate of force development scaling factor (RFD-SF): protocol, reliability, and muscle comparisons. Exp Brain Res. 2011;212(3):359-369. PMID 21656219. DOI 10.1007/s00221-011-2735-7.
- 15 young adults, 125 rapid pulses on 2 days in three muscles including index abduction.
- The slope of peak rate against peak force was reliable with more than 50 pulses (ICC above 0.7) and with 100 to 125 pulses (ICC 0.8 to 0.92).
- Confidence: high. Abstract read. Relevant because Force Pilot has no rapid pulses (see E2).

**A7.12 [Park 2016]** Park SH, Kwon M, Solis D, Lodha N, Christou EA. Motor control differs for increasing and releasing force. J Neurophysiol. 2016;115(6):2924-2930. PMID 26961104. DOI 10.1152/jn.00715.2015. PMC4922612.
- 16 young vs 16 older. Ankle dorsiflexion ramps up and down at 10% MVC/s.
- Force was more variable while releasing than while increasing, in both age groups.
- Confidence: medium. Abstract read.

**A7.13 [Ebisu 2022]** Ebisu S, Kasahara S, Saito H, Ishida T. Decrease in force control among older adults under unpredictable conditions. Exp Gerontol. 2022;158:111649. PMID 34875350. DOI 10.1016/j.exger.2021.111649.
- 8 young vs 10 older. Ankle plantarflexion tracking at low range, high range and pseudo-random.
- RMSE was larger in generation than in release, except the random task in older adults; co-contraction was higher during release.
- Confidence: medium. Abstract read.

**A7.14 [Voelcker-Rehage 2005]** Voelcker-Rehage C, Alberts JL. Age-related changes in grasping force modulation. Exp Brain Res. 2005;166(1):61-70. PMID 16096780. DOI 10.1007/s00221-005-2342-6.
- 14 young vs 12 older. Precision grip sine tracking between 5 and 25% of max, 100 practice trials over 2 days.
- Both groups improved with practice; young improved in generation and release; older adults' release stayed variable. The force range is close to Force Pilot's 8 to 31%.
- Confidence: medium. Abstract read.

**A7.15 [Zatsiorsky 2000]** Zatsiorsky VM, Li ZM, Latash ML. Enslaving effects in multi-finger force production. Exp Brain Res. 2000;131(2):187-195. PMID 10766271. DOI 10.1007/s002219900261.
- 10 healthy adults, maximal presses with every finger combination.
- Non-task fingers reached up to 67.5% of their own single-finger maximum, more for neighbouring fingers.
- Confidence: medium. Abstract read. Measured at maximal effort, so not a direct norm for light-force enslaving.

### A8. Confirmations for other entries flagged in the existing notes (bibliographic check only)

- Enoka RM, Farina D. Force Steadiness: From Motor Units to Voluntary Actions. Physiology (Bethesda). 2021;36(2):114-130. PMID 33595382. DOI 10.1152/physiol.00027.2020. (force-control.md left it unattributed.)
- Sosnoff JJ, Newell KM. Intermittent visual information and the multiple time scales of visual motor control of continuous isometric force production. Percept Psychophys. 2005;67(2):335-344. PMID 15971695. DOI 10.3758/bf03206496.
- Pethick J, Taylor MJD, Harridge SDR. Aging and skeletal muscle force control: Current perspectives and future directions. Scand J Med Sci Sports. 2022;32(10):1430-1443. PMID 35815914. DOI 10.1111/sms.14207. PMC9541459. (Abstract read: older adults show larger and less complex force fluctuations, and short activity interventions can reverse part of this.)
- Hermsdörfer J, Hagl E, Nowak DA, Marquardt C. Grip force control during object manipulation in cerebral stroke. Clin Neurophysiol. 2003;114(5):915-929. PMID 12738439. DOI 10.1016/s1388-2457(03)00042-7.
- Li Y, Lian Y, Chen X, Zhang H, Xu G, Duan H, et al. Effect of task-oriented training assisted by force feedback hand rehabilitation robot on finger grasping function in stroke patients with hemiplegia: a randomised controlled trial. J Neuroeng Rehabil. 2024;21(1):77. PMID 38745227. DOI 10.1186/s12984-024-01372-3.
- Lin CH, Chou LW, Luo HJ, Tsai PY, Lieu FK, Chiang SL, et al. Effects of Computer-Aided Interlimb Force Coupling Training on Paretic Hand and Arm Motor Control following Chronic Stroke: A Randomized Controlled Trial. PLoS One. 2015;10(7):e0131048. PMID 26193492. DOI 10.1371/journal.pone.0131048.
- Hsu HY, Kuo LC, Chiu HY, Jou IM, Su FC. Functional sensibility assessment. Part II: Effects of sensory improvement on precise pinch force modulation after transverse carpal tunnel release. J Orthop Res. 2009;27(11):1534-1539. PMID 19402148. DOI 10.1002/jor.20903.
- Ghai S, Ghai I, Schmitz G, Effenberg AO. Effect of rhythmic auditory cueing on parkinsonian gait: A systematic review and meta-analysis. Sci Rep. 2018;8(1):506. PMID 29323122. DOI 10.1038/s41598-017-16232-5.
- Braun Janzen T, Haase M, Thaut MH. Rhythmic priming across effector systems: A randomized controlled trial with Parkinson's disease patients. Hum Mov Sci. 2019;64:355-365. PMID 30852469. DOI 10.1016/j.humov.2019.03.001.

Count: 94 verified sources in A1 to A7 (26 + 10 + 6 + 16 + 14 + 7 + 15), plus 9 bibliographic confirmations in A8.

---

## B. Mapping table: PD measure to Force Pilot

Notation used in the formulas:

- F(t): task finger force in percent of that finger's own max press, tared per run (the notebook's `percent_trace` and `trial_tare`), resampled to a uniform grid of about 200 Hz (`uniform_grid`).
- T(t): target rebuilt from the run's `waveform_params` (`fp_target_array`). e(t) = F(t) - T(t).
- S: scored samples, meaning the section's samples minus the Stairs step-edge grace windows (`fp_grace_mask`).
- dT/dt: target slope, analytic from the logged section specs or numeric on the grid. "Rising" means dT/dt > +0.5 %/s, "falling" means dT/dt < -0.5 %/s, so holds count as neither.
- Rate measures use a 4th-order zero-phase Butterworth low-pass at 12 Hz before differentiating (Davidson filtered at 12 Hz, Chung at 15 Hz).

Ladder facts the formulas rely on (from `force_pilot.py`, base 8% of max): Slow breath 0.15 Hz sine 8 to 20% (index); Tide ramps at 5 %/s to a 3 s hold at 28% then back (middle); Swell 0.2 Hz sine 8 to 26% (ring); Stairs holds at 14, 20, 26, 20, 14, 8% with 0.6 s grace (little); Hills 5 %/s up and down twice (index); Beach waves 0.333 Hz sine 8 to 22% (middle); Heartbeat four 2 s raised-cosine pulses from 10 to 25% with 1 s rests, peak slope 23.6 %/s (arithmetic: 2π × 0.5 Hz × 7.5%) (ring); Dunes 4 %/s up, 12 %/s down, twice (little); Chop 0.15 plus 0.45 Hz (middle); Open ocean 3 components (ring); Storm and Uncharted 8 components from 0.08 to 0.50 Hz (index). Corridor half-width 8, 6, 5, 4% of max up the ladder. About 8 s of corridor is visible ahead of the craft (`force_pilot_screen.py`, 120 px/s).

| # | PD literature measure (sources) | Force Pilot equivalent today | From saved 200 Hz raw? | Definition or formula |
|---|---|---|---|---|
| 1 | Tracking error, RMSE [Pradhan 2010; Brewer 2009] | Yes: `rmse`, `mae` per run and per section (notebook) | Yes | RMSE = sqrt(mean over S of e²). MAE = mean over S of \|e\|. |
| 2 | Error normalised to peak target, RRMSE [Davidson 2024 OA; Davidson 2025 PD; Davidson 2026] | Not yet computed | Yes | nRMSE = RMSE of a phase / max of T over that phase. Davidson's printed formula may carry an extra scale factor (see E3), so compare ratios and group order, not absolute values. |
| 3 | Time within ±5% of target, %TWR [Davidson papers] | Partly: TIC uses an absolute band of ±8 to ±4% of max | Yes | TWR5 = share of S with \|e\| ≤ 0.05 × T(t). Also report the share with \|e\| ≤ 5% of max, since the papers do not say which band they mean. |
| 4 | Generation vs release error [Davidson 2025 PD; Davidson 2026; Kunesch 1995; Wing 1988; Jordan 1992] | Yes but pooled: `press_mae`, `release_mae` pool Tide (5 %/s), Hills (5 %/s) and Dunes (4 %/s up, 12 %/s down, little finger) | Yes | MAE_rise over rising samples, MAE_fall over falling samples. Release ratio = MAE_fall / MAE_rise. Release difference = MAE_fall - MAE_rise. Compute on symmetric sections only (Tide, Hills, and every sine or multisine), and report Dunes on its own. |
| 5 | Terminal-phase error after release [Davidson 2025 PD] | Not yet computed | Yes | For the hold after a falling section (Tide `low2`, Dunes `end`, Heartbeat `rest1` to `rest4`): CE_term = mean e, MAE_term, TWR5_term. Settle time = first time after the fall ends from which \|e\| ≤ 2% of max for at least 0.2 s. |
| 6 | Trial-to-trial variability of error (iSD) [Davidson 2025 PD] | Not yet computed | Yes, few repeats | SD across repeats of per-repeat RMSE: Hills up1 vs up2 and down1 vs down2, Dunes windward1/2 and slipface1/2, Heartbeat beat1 to 4, and pass 1 vs pass 2 of the same level. |
| 7 | Rate of force rise and relaxation [Neely 2013; Chung 2023; Tobin 2025; Daniels 2024; Stelmach 1989] | Not yet computed | Yes, for guided rates only | Filter, then dF/dt by central difference. Per Heartbeat pulse and per Dunes slipface: peak rise rate, peak fall rate. Rate gain = achieved peak / prescribed peak (23.6 %/s Heartbeat, 12 %/s slipface). |
| 8 | Pulse timing: time to peak, time to relax [Neely 2013; Tobin 2025; Park 2014] | Not yet computed | Yes | Per Heartbeat pulse: peak lag = t(max F) - t(max T). Relaxation time = from max F to the first sample with F ≤ rest level + 10% of pulse height. |
| 9 | Segmentation: steps, pauses, arrests [Naik 2011 (stroke); Howard 2022; Daniels 2024; Pradhan 2015] | Partly: `ramp_segmentation` exists but only matches the legacy names `ramp_up` and `release`, so ladder ramps return nothing | Yes | Pause = run of \|dF/dt\| below a threshold lasting at least 0.15 s inside a ramp. Steps = number of pauses; also mean pause duration. Select ramps by kind and direction (flood, ebb, up*, down*, windward*, slipface*). Report a relative threshold (for example 40% of the prescribed rate) beside the fixed 3 %/s, because 3 %/s is 60% of Tide's 5 %/s. |
| 10 | Amplitude scaling (gain) and phase from a sine fit [Davidson 2026; Brewer 2009; Jordan 1994] | Not yet computed | Yes | Target T = m + A sin(2πft + p). Least-squares fit F = c + a sin(2πft) + b cos(2πft). Gain G = sqrt(a² + b²) / A. Amplitude change = 100 (G - 1)%. Lag τ = wrap(p - atan2(b, a)) / (2πf), positive when force trails. For Chop, Open ocean, Storm and Uncharted, fit every logged component jointly with one sin and cos pair per frequency. |
| 11 | Visuomotor lag [Pradhan 2010; Brewer 2009] | Yes: `lag_ms`, `lag_r` by cross-correlation over the whole run, max 1.5 s | Yes | As now, plus: per level; drop runs with `lag_r` below 0.35 (Brewer's cut-off); report periodic levels (1, 3, 6, 7, 9) apart from non-periodic ones (10, 11, 12) and from step or ramp levels (2, 4, 5, 8). |
| 12 | Signed error: undershoot or overshoot [Jordan 1994; Davidson 2026; Fellows 1998; Fellows 2004; Wenzelburger 2002] | Not yet computed (MAE and RMSE are unsigned) | Yes | CE = mean over S of e, per section. Peak error = max F within ±0.5 s of each target maximum minus that maximum; trough error likewise with minima. |
| 13 | Force steadiness in holds, SD and CV [Vaillancourt 2002; Tobin 2025; Olamazadeh 2026; Chung 2023] | Partly: `cov_hold` averages holds above base + 0.5%, which also takes in Heartbeat's 1 s post-pulse rests | Yes | Tide `slack` (3 s at 28%) and Stairs treads (after grace): drop the first 0.5 s, detrend linearly, SD, CV = 100 × SD / mean. Keep Heartbeat rests for row 5. |
| 14 | Force decay without vision [Vaillancourt 2001a; Jo 2016; Cooke 1978] | Not possible: feedback is never removed (Lighthouse retired) | No | Needs a feedback-blank segment. |
| 15 | Tremor-band power [Brewer 2009 (2 to 8 Hz); Pradhan 2010; Vaillancourt 2001b] | Not yet computed (Lodha bands stop at 1 Hz) | Yes | Welch PSD of detrended e(t) (4 s Hann windows, 50% overlap). Power 2 to 8 Hz and 8 to 12 Hz, each also as a share of 0.1 to 12 Hz power; peak frequency between 3 and 12 Hz. |
| 16 | Force regularity, entropy [Vaillancourt 2001b; Pethick 2022] | Not yet computed | Yes, exploratory | Sample entropy of detrended e(t) with m = 2 and r = 0.2 × SD after resampling to 100 Hz. Report the settings; entropy depends on them and on record length. |
| 17 | Sub-1 Hz spectral shape [Lodha 2013 (stroke); Fox 2013; Baweja 2010] | Yes: `low_n`, `high_n` | Yes | As implemented: share of 0.05 to 4 Hz residual power in 0.1 to 0.3 Hz and 0.5 to 0.8 Hz. No PD evidence; exploratory. |
| 18 | Sequence effect, decrement over repeats [Kang 2010; Tinaz 2016; Espay 2011; Bologna 2020] | Not yet within a run; a block-level fatigue check exists (levels 7 to 9 vs 4 to 6) | Yes | Heartbeat: g_k = max F in pulse k / target peak, k = 1 to 4; slope of g_k on k (Tinaz fitted a line to peaks). Sine levels: peak-to-trough amplitude per cycle, slope on cycle number. |
| 19 | Enslaving: unintended force in other fingers [Park 2012; Park 2014; Vaillancourt 2002; Zatsiorsky 2000] | Not yet computed | Yes: all four pads are in raw.csv (fsr1 to fsr4) | For task finger j, each other finger i in percent of its own max press, tared per run. Regress F_i on F_j over the run, or over its ramps as Park 2014 did over a 12 s ramp, to get slope k_ij. EN_j = mean of k_ij over i ≠ j. Also peak unintended force. Needs every finger's max press for the session (check it is saved). |
| 20 | Multi-finger synergy index [Park 2012; Park 2014] | Not possible: single-finger task | No | Needs a four-finger total-force task with repeated trials. |
| 21 | Dual-task cost [Pradhan 2010; Brewer 2009] | Not possible in this design | No | Needs a concurrent cognitive task. |
| 22 | Practice and retention [Frith 1986; Soliveri 1992; Voelcker-Rehage 2005; Carey 1988; Cristini 2023] | Partly: pass 1 vs pass 2 (T2, T3) and Storm vs Uncharted | Yes for practice; retention needs another day | Per level: pass 2 minus pass 1 for MAE, gain and lag. Storm minus Uncharted error as waveform-specific learning. |
| 23 | Link to clinical severity, MDS-UPDRS-III [Brewer 2009; Tobin 2025; Vaillancourt 2001b; Olamazadeh 2026] | Not applicable in healthy adults | n/a | Spearman correlation with Part III total and hand bradykinesia items in a PD study. |
| 24 | Maximal strength [Park 2012; Park 2014; Tobin 2025] | Partly: max press counts per finger, relative only | Partly | Within-person, within-pad comparisons only; no newtons. |

---

## C. Recommended analysis additions for the healthy baseline

### C0. What separates PD from controls at light force (context for the ranking)

| Measure | Controls | PD | Size of difference | Reliability known? | Source |
|---|---|---|---|---|---|
| Release %TWR, sine 0.2 Hz, 10 to 30% MVC | young 52.4, older 35.2 | 22.6 | all group pairs differ | no | [Davidson 2026] |
| Sine amplitude vs target | young -16.6%, older -26.6% | -39.3% | all group pairs differ | no | [Davidson 2026] |
| Release RRMSE, ramp to 35% MVC | 0.75 | 1.06 | g -1.11 | no | [Davidson 2025 PD] |
| Terminal-phase %TWR after release | 81.4 | 51.0 | g 1.11; trial-to-trial SD g -1.27 | no | [Davidson 2025 PD] |
| Fastest relaxation rate from 15% MVC | -57.4 %MVC/s | -43.2 %MVC/s | p = 0.001 | no | [Chung 2023] |
| CV of force, index abduction at 15% MVC | 3.39% | 5.67% | significant; RBD higher still | no | [Tobin 2025] |
| Segmentation in rapid pulses | older adults low | higher | d above 0.8 | yes, day to day (tested against ICC above 0.8) | [Howard 2022] |
| Tracking RMSE, lag, 2 to 8 Hz tremor | lower | higher | RMSE and lag P < 0.001; within PD the measures predicted about 76% of UPDRS variance | no | [Pradhan 2010; Brewer 2009] |
| Force regularity (approximate entropy) | higher | lower | significant; within PD r² = 0.71 with UPDRS motor | no | [Vaillancourt 2001b] |
| Enslaving | lower | higher | significant | no | [Park 2012] |

Light-force coverage: PD deficits have been shown at 5 to 50% MVC holds [Vaillancourt 2001a; 2001b; 2002], 10 to 20% [Olamazadeh 2026], 15% [Neely 2013; Chung 2023; Tobin 2025] and 10 to 35% tracking [Davidson papers]. Force Pilot's 8 to 31% of max sits inside that range.

### C1 to C11, ranked by value

**C1. Clean press vs release split (fixes F3).**
- What: rising vs falling error on symmetric shapes only (Tide, Hills, and the rising and falling halves of every sine and multisine), as ratio and paired difference, per finger. Dunes reported separately as a rate effect.
- Why: release-specific loss is the lead PD finding [Davidson 2025 PD; Davidson 2026; Kunesch 1995; Wing 1988] and an ageing finding [Davidson 2024 OA]. The pooled `release_mae` mixes Dunes' 12 %/s drop on the little finger with 4 to 5 %/s climbs. Arithmetic: a 150 ms lag alone gives ramp error of about 0.75% of max at 5 %/s and 1.8% at 12 %/s, so Dunes can push release minus press toward the 2% F3 margin with no release deficit at all. Sine halves have matched rate profiles by construction, which is how [Davidson 2026] split generation and release.
- Healthy reference: young adults release about equal to or slightly better than generation: RRMSE 0.38 vs 0.42 and %TWR 52.4 vs 47.0 on a 0.2 Hz sine [Davidson 2026]; RRMSE 0.39 vs 0.47 and %TWR 50.1 vs 44.3 on ramps [Davidson 2024 OA]. Against that, force is more variable during release in young and old ankles [Park 2016]. Expect a ratio near 1.
- Effort: low (sign of dT/dt on the existing rebuilt target).

**C2. Sine-fit gain and phase per level, which gives each person a frequency response.**
- What: row 10 of Table B for Slow breath (0.15 Hz), Swell (0.2 Hz), Beach waves (0.333 Hz), Chop (0.15 and 0.45 Hz), and every multisine component (0.08 to 0.50 Hz).
- Why: reduced amplitude was the measure that separated all three groups in [Davidson 2026]; RMSE in PD tracking is mostly undershoot [Brewer 2009]; reduced amplitude is a core part of bradykinesia [Bologna 2020; Espay 2011]. Swell is the direct analogue of Davidson's task (0.2 Hz, 8 to 26% vs 10 to 30%).
- Healthy reference: young adults undershot amplitude by 16.6 ± 4.1% (gain about 0.83) with phase and frequency error near zero at 0.2 Hz with 4 s of preview [Davidson 2026]. Expect gain to fall and lag to grow with frequency, more steeply on non-periodic targets; this fits [Cathers 1996] but is not a published value for this task.
- Caveat: Storm and Uncharted components are 0.05 to 0.07 Hz apart, at or below the 0.071 Hz resolution of a 14 s run (arithmetic), so use a joint least-squares fit and pool the two levels; do not read FFT bins.

**C3. Literature-compatible accuracy numbers beside TIC and MAE.**
- What: TWR5 (row 3) and nRMSE (row 2) per phase and level.
- Why: TIC uses an absolute corridor of ±8 to ±4% of max, which cannot be set against Davidson's ±5% of target. A normative study needs at least one number that sits next to a published healthy value.
- Healthy reference: young adults %TWR about 47 to 52 on the sine and 44 to 75 on ramp phases [Davidson 2026; Davidson 2024 OA]. At a 20% target, ±5% of target is ±1% of max (arithmetic), much tighter than the corridor, so TWR5 will sit far below TIC.

**C4. Signed error and turnaround errors.**
- What: row 12, per section and at every target peak and trough.
- Why: PD errors have a direction that MAE hides: undershoot in visually guided tracking and non-visual targets [Davidson 2026; Jordan 1994], excess force when gripping objects [Fellows 1998; Fellows 2004], and overshoot ON in people with dyskinesia [Wenzelburger 2002].
- Healthy reference: near-zero bias on holds; a small undershoot of sine peaks is expected (see C2).

**C5. Segmentation on the ladder ramps.**
- What: row 9, with the name filter extended to ladder sections and both a fixed and a relative pause threshold; also steps per ramp and mean pause duration.
- Why: segmentation separated PD from age-related slowing with large effects and good day-to-day reliability [Howard 2022], appears in rapid PD handgrip [Daniels 2024], counted arrests tracked PD severity [Pradhan 2015], and it beat RMSE in stroke [Naik 2011].
- Healthy reference: no numeric healthy step counts were readable (abstracts only). The cohort itself sets the device's healthy threshold, which is useful work for the thesis.
- Caveat: pad noise is 1.2 to 1.5 counts, and thresholds are uncalibrated; check the pause rate on Tide holds, where none should occur.

**C6. Guided rate, pulse timing and terminal settle.**
- What: rows 5, 7 and 8 on Heartbeat pulses, Dunes slipfaces and the holds after them.
- Why: slow relaxation is the most repeated PD force finding, present even early [Chung 2023; Neely 2013; Tobin 2025; Jordan 1992; Wing 1988], it responds to dopamine [Jordan 1992; Fischer 2019; Park 2014], and the terminal phase gave the largest PD effects in ramp tracking [Davidson 2025 PD].
- Healthy reference: older healthy adults relaxed from 15% MVC at about 57 %MVC/s when told to go as fast as possible [Chung 2023]. Force Pilot asks for at most 23.6 %/s, so young adults should show rate gain near 1 with small peak lag; older controls held about 81% of the terminal phase within ±5% of target [Davidson 2025 PD].
- Caveat: Force Pilot prescribes the rate. Even early PD relaxed at about 43 %MVC/s [Chung 2023], well above 23.6 %/s, so these guided measures may not reach the PD deficit (see D4).

**C7. Within-run decrement (sequence effect).**
- What: row 18.
- Why: decrement is typical of PD bradykinesia and is not fixed by levodopa [Bologna 2020; Kang 2010; Espay 2011]; visual feedback flattened it [Tinaz 2016].
- Healthy reference: with continuous visual feedback, expect a slope near zero [Tinaz 2016 found feedback reduced decrement in controls too]. No numeric healthy slope was extracted.
- Caveat: four pulses per run is a thin base; pool across passes.

**C8. Enslaving index from the non-task pads.**
- What: row 19.
- Why: PD shows more enslaving and less finger independence [Park 2012; Vaillancourt 2002], and it did not change with levodopa [Park 2014], so it behaves like a trait marker. The data are already recorded.
- Healthy reference: at maximal effort non-task fingers reach up to 67.5% of their own max, more for neighbours [Zatsiorsky 2000]. The regression-based index in PD was about 0.07 to 0.09 [Park 2014]; I did not verify a healthy young value for that index, so the cohort would supply the device's own norm.
- Caveat: rule out mechanical cross-talk first (load one pad with a weight and read the others), and note that a flat-hand press differs from Latash's finger-sensor posture.

**C9. Lag read per level class.**
- What: row 11 with the r floor and the class split.
- Why: PD and controls both use prediction on periodic targets [Day 1984; Bloxham 1984], PD lag is longer on mixed targets [Pradhan 2010], and the corridor shows about 8 s ahead, so periodic levels can be flown with little lag. F2's 100 to 300 ms band fits non-periodic levels; periodic levels may fall below it for good reasons.
- Healthy reference: lag under 20 ms on repeated patterns [Day 1984]; near-zero phase error at 0.2 Hz [Davidson 2026]; visual integration about 150 ms [Slifkin 2000]; tracking refractory delay about 170 ms [Miall 1993].

**C10. Tremor-band power and regularity (exploratory).**
- What: rows 15 and 16.
- Why: 2 to 8 Hz power helped predict UPDRS [Brewer 2009] and was higher in PD [Pradhan 2010]; regularity separated PD while amplitude did not [Vaillancourt 2001b].
- Healthy reference: small power with any peak in the 8 to 12 Hz physiological band; no device-specific norm exists. Runs of 13 to 16 s limit spectral and entropy estimates, so pool runs.

**C11. Reliability and practice framing for T2 and T3.**
- What: pass 2 minus pass 1 per level for MAE, gain and lag; ICC with the practice shift reported, not hidden.
- Why: healthy tracking and steadiness improve on retest within 20 minutes to a week [Carey 1988; Blomkvist 2018; Voelcker-Rehage 2005], and CV-type measures reproduce better than area-type error measures [Blomkvist 2018]. A shift is expected and is not a failure.
- Healthy reference: CV ICC about 0.81 vs 0.46 for area between curves [Blomkvist 2018]; rapid-pulse rate slope ICC 0.8 to 0.92 with 100 or more pulses [Bellumori 2011].

### C12. Healthy-adult reference values in one place

| Measure | Value | Population and task | Source | Comparability to Force Pilot |
|---|---|---|---|---|
| Release vs generation RRMSE | 0.38 vs 0.42 | 10 young, grip sine 0.2 Hz, 10 to 30% MVC | [Davidson 2026] | Grip, 30 Hz; ratios comparable, absolute values not |
| Release vs generation %TWR | 52.4 vs 47.0 | same | [Davidson 2026] | band is ±5% of target |
| Ramp phases RRMSE (gen, hold, release) | 0.47, 0.24, 0.39 | 10 young, ramp to 35% at about 10 %/s | [Davidson 2024 OA] | Tide and Hills run at 5 %/s |
| Ramp phases %TWR | 44.3, 75.4, 50.1 | same | [Davidson 2024 OA] | as above |
| Sine amplitude | -16.6 ± 4.1% | 10 young, 0.2 Hz | [Davidson 2026] | Swell is the analogue |
| CV at low force | 4.9% at 2% MVC; 1.4% at 15%; 1.2 to 1.9% above | young, index abduction, steady holds | [Moritz 2005] | different muscle; long holds |
| CV with vision on | 4.8% (2.5% MVC), 3.2% (30%), 3.5% (65%) | 27 young, index abduction | [Tracy 2015] | as above |
| CV at 15% MVC | 3.39 ± 1.86% | 27 healthy, mean age 63 | [Tobin 2025] | older than the cohort |
| SD at 15% MVC | 0.65 ± 0.21 %MVC (CV about 4.4%, arithmetic) | 21 healthy older, pinch pulses | [Chung 2023] | 2 s pulses |
| Fastest relaxation and rise | -57.4 and 38.3 %MVC/s | healthy older, pinch to 15% | [Chung 2023] | ballistic, not guided |
| Lag on repeated pattern | under 20 ms | controls and PD, wrist | [Day 1984] | predictable levels |
| Visual integration interval | about 150 ms; corrections near 1 Hz | adults, holds | [Slifkin 2000] | non-periodic levels |
| Effect of visual gain | SD 0.09 to 0.06 N, low to moderate gain | 14 young, 2 and 10% MVC | [Baweja 2010] | gain fixed at 1.0 in the battery |
| Enslaving at maximal effort | up to 67.5% of own max | 10 adults | [Zatsiorsky 2000] | maximal, not light force |
| Reliability of CV vs area error | ICC about 0.81 vs 0.46 | young and older, handgrip | [Blomkvist 2018] | area is close to MAE |

---

## D. Thesis notes (bullets, not prose)

### D1. Rationale and background

- PD bradykinesia is slowness, smaller amplitude and a decrement across repeats [Bologna 2020]. Clinicians rate it by eye on ordinal items in MDS-UPDRS Part III [Goetz 2008]; instrumented force tasks give continuous numbers instead [Pradhan 2010; Brewer 2009].
- Basal ganglia set grip force parameters [Prodoehl 2009]. Drug-naive PD under-activate them during grip pulses, more so when the task switches between contraction and relaxation [Spraker 2010]. Release uses partly different circuits from generation [Spraker 2009].
- The most repeated PD force findings at light force: slow or imprecise release [Wing 1988; Jordan 1992; Kunesch 1995; Neely 2013; Chung 2023; Tobin 2025; Davidson 2025 PD; Davidson 2026], reduced amplitude or undershoot [Davidson 2026; Brewer 2009; Jordan 1994], and in some cohorts more variability [Vaillancourt 2002; Tobin 2025].
- Force Pilot's sections line up with those findings: ramps and sine halves (release vs press), holds (steadiness), sines (amplitude, lag), pulses (rate, decrement), four pads (enslaving [Park 2012]).
- Why a visible target path: people with PD lean on vision [Flowers 1976; Cooke 1978], lose force faster when it is removed [Vaillancourt 2001a; Jo 2016], and are less impaired on externally guided than self-initiated action [Jahanshahi 1995; Redgrave 2010]. Visual feedback reduced the grip-force decrement [Tinaz 2016].
- Why feedback-rich practice: PD retention deficits disappear with augmented feedback during practice [Cristini 2023]; PD learned better with feedback on every trial [Guadagnoli 2002].
- Why light force: Force Pilot runs at 8 to 31% of max, the band where PD deficits have been measured (C0), and upper-limb steadiness in that band relates to function in older adults (r = 0.58) [Camacho-Villa 2025].
- Training evidence is indirect: hand training gives a small dexterity gain in PD [Proud 2024]; handwriting amplitude training against visual targets transferred and was retained [Nackaerts 2016a]; finger force feedback training helps after stroke [Seo 2025]. No PD force-tracking training trial exists (E2).

### D2. Discussion points for the healthy results

- F3: a young-adult release roughly equal to press, or slightly better, would match [Davidson 2024 OA; Davidson 2026]; greater release variability would match [Park 2016]. Read F3 on symmetric shapes (C1) before interpreting any pooled release excess.
- Gain: a young cohort should still undershoot sine peaks (about 17% at 0.2 Hz in [Davidson 2026]). Matching that on Swell would show the device reproduces a published healthy value.
- Lag: small lag on periodic levels and larger on multisines is what prediction plus preview predicts [Day 1984; Bloxham 1984; Cathers 1996]; this is also the axis on which PD findings conflict (E1.6).
- TIC is not %TWR: set TWR5 and nRMSE beside the published values (C3), and keep TIC for the within-level game reading.
- Steadiness: compare hold CV with 1.4 to 4.8% in young adults [Moritz 2005; Tracy 2015], noting a different muscle and shorter holds.
- Pass 2 better than pass 1 is expected practice [Carey 1988; Blomkvist 2018; Voelcker-Rehage 2005]; the within-session ICC is an upper bound on between-day reliability (the baseline study already says this).
- Enslaving, if computed, gives a device-specific norm for a measure PD raises [Park 2012] and levodopa leaves unchanged [Park 2014].
- Game design: Force Pilot rewards accuracy at set speeds, the opposite of the speed-driven games that raised tapping speed, lowered tapping accuracy and left peg-test scores unchanged [Allen 2017]; that matches the "task specificity" call in [Garcia-Agundez 2019].

### D3. Limitations

- Healthy young adults only; no PD participants; large age gap to PD cohorts (for example 67 y in [Davidson 2026]), and older adults differ from young on most of these measures [Davidson 2024 OA; Davidson 2026].
- Different effector and reference: flat single-finger press on a SingleTact pad, percent of own max press, against precision grip, pinch, index abduction or handgrip at percent MVC in the literature.
- Short runs (13 to 16 s), one run per level per pass, against ten 32 s trials in [Davidson 2026]; spectral, entropy and per-level estimates are noisy.
- Prescribed rates of at most 23.6 %/s sit below what even early PD can do when told to go fast (about 43 %MVC/s relaxation [Chung 2023]), so rate deficits may not show.
- Feedback is always on, so memory-guided decay [Vaillancourt 2001a; Jo 2016] cannot be measured.
- About 8 s of preview makes the multisines non-periodic but visible, unlike no-preview pseudorandom targets [Brewer 2009].
- Fixed ladder order and finger table confound level with time on task and with finger (as `force_pilot.py` already states).
- Background music plays during Force Pilot blocks by default; in PD, rhythmic sound can act as a cue [Spaulding 2013], so it should be off for PD work (the EEG config already turns it off).
- No clinical comparator, no responsiveness data, no retention test; PD retention of new skills is a known weak point [Marinelli 2017; Cristini 2023].

### D4. Future work, and what testing PD use would need

- Cross-sectional PD vs age-matched control study first: H&Y I to III; MDS-UPDRS-III by a trained rater [Goetz 2008]; levodopa equivalent dose; OFF (at least 12 h withdrawal as in [Davidson 2025 PD], overnight in [Neely 2013; Chung 2023]) and ON sessions; the more affected hand; retest on a separate day; safety and consent handled as standard procedure.
- Sample size (arithmetic, normal approximation, two-sided α 0.05, power 0.8, n per group ≈ 15.7 / d²): d = 1.1, the size of the release effects in [Davidson 2025 PD], needs about 14 per group; d = 0.8 about 26; d = 0.5 about 64 (rounded up, plus one for the t distribution).
- Task additions for PD: a fast-release level or "as fast as possible" pulses on the 2 s on, 1 s off pattern of [Neely 2013; Chung 2023] to reach the relaxation deficit; brief feedback-blank windows of 1 to 2 s (not the retired 16 s Lighthouse hold) for decay; keep corridors moderate, because tight visual targets can shrink movement in PD [Nackaerts 2016b].
- Visual gain has not been studied in PD; it helps young and stroke hands [Baweja 2010; Archer 2018] but magnification made older hands more variable at very low force [Fox 2013; Tracy 2015], so test it before using it as a difficulty lever.
- Only after measurement work, a training study: feasibility, then an RCT with an active control, dexterity outcomes (nine hole peg, Purdue), and retention and transfer tests [Proud 2024; Vanbellingen 2017; Allen 2017]. Feedback schedule: frequent concurrent feedback suits PD [Guadagnoli 2002; Cristini 2023], but add no-feedback probes because gains can stay tied to the feedback [Verschueren 1997; Nieuwboer 2009].
- Multi-finger and dual-task variants as extra PD probes [Park 2012; Pradhan 2010].
- The corridor-exit buzz is tactile error feedback with no PD hand evidence; PD vibrotactile work is mostly gait [Goncalves 2021].

---

## E. Conflicts and gaps

### E1. Where the literature disagrees

1. **Release vs press in healthy adults.** Young adults were slightly better in release on precision grip [Davidson 2024 OA; Davidson 2026]. Force was more variable in release in young and older ankles [Park 2016]. Generation RMSE exceeded release in ankle tracking [Ebisu 2022]. The direction depends on effector and on whether error or variability is measured, which suits F3's equivalence framing.
2. **Is release selectively impaired in PD?** Yes: [Wing 1988; Kunesch 1995; Davidson 2025 PD], and in the hand only relaxation was slower [Chung 2023]. No or not only: onset and release were both slow [Jordan 1992; Neely 2013; Tobin 2025; Daniels 2024], and in [Davidson 2026] RRMSE showed no phase interaction; only time near target did.
3. **Force variability in PD.** Higher [Vaillancourt 2002; Tobin 2025], and higher with severity [Olamazadeh 2026]. Similar to controls [Chung 2023; Stelmach 1989 across trials; Vaillancourt 2001b for tremor amplitude]. More low-frequency variability went with less impairment [Ko 2015]. It is also not PD-specific: RBD was more variable than PD [Tobin 2025] and essential tremor more than PD [Poon 2011].
4. **Too much force or too little.** Excess grip force when lifting and holding objects [Fellows 1998; Fellows 2004] and overshoot ON in dyskinetic patients [Wenzelburger 2002], against undershoot in visually guided tracking and non-visual targets [Davidson 2026; Brewer 2009; Jordan 1994]. The task (safety margin vs tracking) and medication state decide the sign.
5. **Medication.** Improves rates, speed and synergies [Jordan 1992; Fischer 2019; Park 2014; Johnson 1996 for velocity]. Does not improve tracking error [Johnson 1996], the decrement [Kang 2010; Espay 2011; Bologna 2020], enslaving [Park 2014] or isometric task performance in early PD [Jordan 1994]. One study found no PD vs control force control difference at all [Stewart 2009]. The decrement was worse ON without feedback [Tinaz 2016].
6. **Prediction vs visual dependence.** PD act as if steered by vision and do poorly when it is removed [Flowers 1976; Cooke 1978]. PD can predict periodic targets and remove lag [Day 1984; Bloxham 1984].
7. **Do visual cues help?** Visual feedback reduced the decrement [Tinaz 2016] and cues help performance [Nieuwboer 2009; Spaulding 2013]. Tight visual targets shrank movement [Nackaerts 2016b], and learning stayed tied to augmented feedback [Verschueren 1997].
8. **Learning and retention in PD.** Relatively preserved, only slower [Nieuwboer 2009; Felix 2012; Frith 1986; Soliveri 1992]. Retention reduced, even early [Marinelli 2017], though task-specific and removable with augmented feedback [Cristini 2023].
9. **Links to severity.** Found for tracking composites, regularity, CV, arrests and rate [Brewer 2009; Vaillancourt 2001b; Tobin 2025; Olamazadeh 2026; Pradhan 2015; Jordan 1992]. Absent for the decrement and for force excess [Tinaz 2016; Wenzelburger 2002]. Samples are small and tests many; [Brewer 2009] fitted 36 predictors on 26 people.
10. **Games and technology for PD hands.** Small positive pooled effect on dexterity [Proud 2024] and positive small trials [Cetin 2024; Vanbellingen 2017, not retained at 12 weeks]. Null or no between-group difference [Allen 2017; Heinzle 2026; Tao 2024 for upper-limb robotics]. VR reviews report gains but on low-quality evidence [Lahude 2023; Fernandez-Gonzalez 2023; Dockx 2016].
11. **Visual gain.** More gain lowered error and variability in young and stroke hands [Baweja 2010; Archer 2018]. Magnification made older hands more variable at very low force [Fox 2013; Tracy 2015]. No PD study found.

### E2. Gaps

- No trial of isometric finger force-tracking training in PD was found. PubMed searches run 25 September 2026 included: `Parkinson*[tiab] AND ("force tracking" OR "force-tracking" OR "visuomotor tracking" OR "force control training" OR "grip force training" OR "pinch force training")[tiab] AND (training OR practice OR intervention OR rehabilitation)[tiab]` (3 hits, none relevant) and title-field combinations of Parkinson with training, practice, exercise, rehabilitation, biofeedback and force, grip, pinch, isometric, tracking, visuomotor (12 hits, none relevant). The nearest PD evidence is handwriting amplitude training [Nackaerts 2016a] and general hand training [Proud 2024].
- No PD data for single-finger flexion presses of the middle, ring or little finger; PD force work uses precision grip, pinch, index abduction or handgrip.
- No PD test-retest reliability for tracking measures; the reliable PD measures are rapid-pulse segmentation [Howard 2022].
- No PD study of visual gain.
- No PD data on multisine tracking with preview; the closest is pseudorandom tracking without preview [Pradhan 2010; Brewer 2009].
- No verified healthy young values for regression-based enslaving or for release vs press on flat-finger pads; this cohort would supply them.
- The Lodha sub-1 Hz bands are a stroke measure with no PD evidence [Lodha 2013].
- Force Pilot has no rapid pulses, so rate-scaling measures with known reliability [Bellumori 2011] and the ballistic PD paradigms [Neely 2013; Chung 2023; Tobin 2025] have no direct counterpart.

### E3. Items I could not verify (not used as evidence)

- Pinto Neto O, Brizzi ACB, Campos SF, Sales MP, de Almeida FD, Pedroso W, et al. (2026). Influence of visual feedback, hand dominance, and disease severity on grip force control and tremor dynamics in Parkinson's disease: A cross-sectional secondary analysis. Arch Gerontol Geriatr Plus 3:100309. DOI 10.1016/j.aggp.2026.100309. Found on Crossref; not in PubMed; the publisher page refused access, so the content is unread. Its topic matches item 4 of the brief, so obtain it through the library.
- Flowers K (1978). Some frequency response characteristics of Parkinsonism on pursuit tracking. Brain 101(1):19-34. PMID 638724. The record exists but has no abstract, so its findings are not used.
- Individual ICC values in [Howard 2022], numeric results in [Pradhan 2010] and rate values in [Neely 2013] were not readable (paywall or figures only).
- Davidson's RRMSE formula divides by T, "the time of the trial", while summing 30 Hz samples. If T is in seconds, the published values are about 5.5 times RMSE / peak target (my inference, not stated by the authors). Compare ratios, not raw RRMSE.
- McRuer and Jex (1967), cited in `force_pilot.py` through Drop et al. (2016), was not re-checked (not PD, not in PubMed).

### E4. Corrections to the existing notes and code observations

The note and docstring corrections below were applied on 25 September 2026 (force_pilot.py, stroke.md, ranked.md, movement-disorders.md, force-control.md, healthy_baseline_study.txt).


- `force_pilot.py` docstring says of [Taud 2021] that grip-force tracking training "itself drove motor recovery". In that RCT every arm received the training and only tDCS was randomised; trained-task gains were independent of tDCS and no arm improved on the Wolf Motor Function Test. There was no untrained control, so the trial cannot show training causes recovery. Suggested wording: the training was feasible and trained-task performance improved; its effect on recovery was not tested.
- `healthy_baseline_study.txt` F3 cites Davidson 2026 and Naik 2011 for a "Parkinson's and ageing marker". Naik 2011 is stroke. The ageing source is [Davidson 2024 OA]; the PD sources are [Davidson 2025 PD] and [Davidson 2026].
- movement-disorders.md: the 2024 "Grip force release is impaired..." paper is Davidson S, Learman K, Zimmerman E, Rosenfeldt AB, Alberts JL, Exp Brain Res 243(1):16 (online 5 December 2024; cited by its authors as 2025).
- force-control.md: Archer is 2018 (volume 17, online 2017); its 21, 6 and 3% MVC figures are confirmed. The "Rate control deficits" paper is [Chung 2023]; the "Measures of motor segmentation" paper is [Howard 2022]; the steadiness meta-analysis is [Camacho-Villa 2025]; the BMC reproducibility study is [Blomkvist 2018]; the magnified-feedback paper is [Fox 2013]; the Eur J Appl Physiol 2010 paper is [Baweja 2010]; the Physiology review is Enoka and Farina 2021 (A8).
- The brief describes the corridor as narrowing "from 8 to 4 percent of max"; in the code those are half-widths (`hw_pct`), so the full corridor is 16 to 8% of max.
- Notebook observations:
  - `ramp_segmentation` only matches sections named `ramp_up` or `release` (the legacy plan), so every ladder run has empty step counts.
  - `press_mae` and `release_mae` pool Tide, Hills and Dunes, so release includes Dunes' 12 %/s slipface on the little finger against a 4 %/s climb (see C1 for the size of this).
  - `cov_hold` and `hold_mae` include Heartbeat's 1 s rests at base + 2%, which are post-release settles, so relaxation transients enter the steadiness number.
  - Lag is computed per whole run and F2 takes the median over all runs, mixing periodic, non-periodic, step and ramp levels.
  - Storm and Uncharted components sit closer together than one run's frequency resolution (C2).

All five notebook observations are fixed in `analysis/session_analysis.ipynb` (25 September 2026): segmentation reads every task ramp, press and release read the symmetric shapes only with Dunes apart, steadiness reads the raised holds of 2 s or more, lag is read per wave class with F2 on the non-periodic waves, and Storm and Uncharted are fitted jointly. The new chapter is `sec_force_pilot_pd`.

### E5. What the first real ladder runs showed (25 September 2026)

Three blocks of the author's own pilot data (22 runs, 2 people) were re-scored with the new code before anything was fixed. They showed four problems no paper could have flagged, because each comes from this device or this task.

- The zero was wrong. The notebook re-tared each run from the second before it began, and players press toward the 8% first hold during that second, since the corridor shows about 8 s ahead. Error moved by up to 5.6% of max and time in corridor by up to 0.47 against the game's own score. The game logs its zero now (`ref_counts`), older runs rebuild it at the announce card's opening, and the offline score matches the game to a median 0.03% of max. Two game-side changes came with it: force is clamped at zero as the game shows it, and a finger flying two levels in a row (Storm into Uncharted) keeps its rested zero.
- The lag estimator was biased. It summed the cross-correlation over a shrinking overlap, which puts a cusp at zero lag on any wave whose two ends sit on the same side of the mean. Every ramp level read 0 ms, and a synthetic Tide read 0 ms for true lags of 50, 150 and 250 ms. Each lag is now a Pearson r over the overlapping samples.
- The 12 Hz filter Davidson used is too wide for rates on these pads. Rate fluctuation on holds was 8.7 %/s at a 3 Hz cut-off and 17 %/s at 12 Hz, larger than the 5 %/s ramps, and a peak rate read up to 3.7 times the rate asked for. Rates now use a 5 Hz low-pass and 20 to 80% transition times (arithmetic check: a 0.5 Hz raised cosine loses nothing below 5 Hz). Pauses on a 5 %/s ramp partly count the normal start-stop of visual correction, so segmentation here is a device norm, not Howard 2022's rapid-pulse measure.
- The corridor changes what amplitude means. It scores being inside it, and at the easy levels it is wider than the wave, so a player can stay inside while making the wave smaller. The author's sine gain was 0.5 to 0.8 against Davidson's 0.83 in young adults. Gain and the 5% bands read the corridor as much as the hand; Davidson scored error against the line itself.

Also: three runs ended a real block with the finger never pressing (levels 10 to 12). Kept in, they would have faked an error rise with level and propped up F1. Runs whose 95th percentile of force is under 2% of max are now left out as idle, like demo runs.

These belong in the methods (the zero and the lag estimator) and the limitations (the filter, the corridor and amplitude, the pad noise floor under every SD and 5% band) of the thesis.
