# Provenance and decision record

## Role map

- Exact role: **Computational Neuroscience Intern - Data Analysis and Modeling**.
- Primary work mode: computational neuroscience / data analysis.
- Core duties demonstrated: process whole-brain calcium recordings; analyze a neuronal connectivity graph; build and evaluate a circuit-state model; implement an interactive visualization; turn results into a testable perturbation shortlist.
- The main interaction directly covers the two central duties by joining state-dependent calcium activity to anatomical connectivity and changing the candidate perturbation when the evidence balance changes.

## Recipient-value brief

- **Lab decision:** which measured neuron is the most informative first perturbation for separating a behavior-state transition from a highly connected but nonspecific hub.
- **Useful output:** a ranked neuron and direction-of-perturbation shortlist with anatomy, activity, cross-recording agreement, and an explicit follow-up readout.
- **Added contribution:** Cathy joins two public datasets that are normally inspected separately and adds a sensitivity analysis plus held-out sequence-model comparison.
- **Capability proof:** the functioning analysis uses Python numerical processing, graph metrics, state aggregation, cross-validation, and a target-owned Clone-Structured Cognitive Graph implementation.
- **Next action:** repeat the shortlisted perturbation in calcium-imaged animals and test whether the transition probability changes while monitoring the specified alternative state.

Value score: lab relevance 2; added contribution 2; interactive utility 2; Cathy capability 2; scientific credibility 2. **Total: 10/10.**

## Data and code

- Kato et al. 2015 processed wild-type, no-stimulus whole-brain calcium data: OSF `2395t`, file `WT_NoStim.mat`, SHA-256 `7531811c1718e26a0455f59cb2f8188cf25809278cfea85770dfe03315a0098a`.
- Varshney et al. 2011 chemical and gap-junction matrices: `lrvarshney/elegans`, commit `07d10c2d43b3da9a1fefed2e8658a98dc4310765`, files `ConnOrdered_040903.mat` and `NeuronTypeOrdered_040903.mat`.
- Astera Institute-owned CSCG fork: `Astera-org/naturecomm_cscg`, commit `66c81ea061314d85dd305cfc7deced5b573296dd`. README, MIT license, requirements, core model file, and recent history were inspected. The model was executed directly on the five Kato behavior-state sequences with 1, 2, and 3 clones per observed state in leave-one-recording-out evaluation.
- The Astera fork currently matches its upstream Vicarious implementation at the pinned commit; no DynamoBrain-specific repository was found through the official Astera GitHub organization or exact project search.

## Transformations

1. Bleach-corrected calcium traces were z-scored within neuron and recording.
2. For each transition, source and target activity were averaged within each recording, then averaged across only identified neurons present in at least two recordings and in the connectome.
3. Anatomical strength is total incoming and outgoing chemical-synapse weight plus electrical-junction weight. Percentiles are computed over the 279-neuron graph.
4. Candidate ranking keeps activity magnitude, cross-recording agreement, coverage, and anatomical strength separate so the browser can recompute the shortlist under a user-chosen evidence balance.
5. CSCG models were trained on four recordings and scored on the held-out fifth. A dedicated boundary action prevents concatenation boundaries from being learned as biological transitions. Lower bits per step is better.

## Limits

- Kato recordings contain 629 neuron ROIs across five animals, but only a subset is confidently named, and named coverage differs by animal.
- The anatomical matrix predates the Kato recordings and does not encode synaptic sign, state dependence, or inter-animal variation.
- Calcium activity is slow and observational. A high score nominates a perturbation to test; it does not establish causal control.
- The CSCG analysis models annotated behavior-state sequences, not the raw calcium trajectories, and its small held-out sample is a method check rather than a definitive model comparison.
