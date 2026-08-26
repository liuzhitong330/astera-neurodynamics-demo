# Astera neurodynamics demo

A role-specific exploratory analysis prepared by Cathy Liu for Astera Institute's **Computational Neuroscience Intern - Data Analysis and Modeling** opening.

The page combines:

- five processed whole-brain calcium-imaging recordings from Kato et al. 2015 (OSF `2395t`);
- the 279-neuron weighted chemical and gap-junction matrices from Varshney et al. 2011;
- leave-one-animal-out evaluation using Astera Institute's public Clone-Structured Cognitive Graph implementation.

The main interaction changes a perturbation shortlist as the reader moves between activity evidence and anatomical connectivity. The second analysis tests whether extra latent context improves held-out behavior-state prediction.

Live demo: <https://liuzhitong330.github.io/astera-neurodynamics-demo/>

## Reproduce the derived data

The original data files are excluded from the repository. Download `WT_NoStim.mat` and `readme_Kato2015.txt` from [OSF 2395t](https://osf.io/2395t/), and copy `ConnOrdered_040903.mat` plus `NeuronTypeOrdered_040903.mat` from [`lrvarshney/elegans`](https://github.com/lrvarshney/elegans) into `source-data/`. Clone [`Astera-org/naturecomm_cscg`](https://github.com/Astera-org/naturecomm_cscg) at commit `66c81ea061314d85dd305cfc7deced5b573296dd` to `/private/tmp/astera_naturecomm_cscg`, then run:

```bash
python3 analysis/build_dataset.py
```

See [`analysis/PROVENANCE.md`](analysis/PROVENANCE.md) for the role map, transformations, hashes, scientific limits, and value decision record.
