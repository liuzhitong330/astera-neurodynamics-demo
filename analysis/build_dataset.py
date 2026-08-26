#!/usr/bin/env python3
"""Build the compact browser dataset for the Astera neurodynamics demo.

Inputs are kept in source-data/ and excluded from the published repository.
The output is a small data.js file containing checked, derived statistics.
"""

from __future__ import annotations

import json
import math
import re
import sys
import types
from collections import Counter, defaultdict
from pathlib import Path

import h5py
import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source-data"
KATO = SOURCE / "WT_NoStim.mat"
CONNECTOME = SOURCE / "ConnOrdered_040903.mat"
ASTERA_CSCG = Path("/private/tmp/astera_naturecomm_cscg")

STATE_ORDER = ["fwd", "slow", "rev1", "rev2", "revsus", "dt", "vt", "nostate"]
STATE_LABELS = {
    "fwd": "Forward",
    "slow": "Slowing",
    "rev1": "Reverse 1",
    "rev2": "Reverse 2",
    "revsus": "Sustained reverse",
    "dt": "Dorsal turn",
    "vt": "Ventral turn",
    "nostate": "Ambiguous",
}
TRANSITIONS = {
    "fwd_rev": ("Forward to reverse", ["fwd"], ["rev1", "rev2", "revsus"]),
    "rev_turn": ("Reverse to turn", ["rev1", "rev2", "revsus"], ["dt", "vt"]),
    "turn_fwd": ("Turn to forward", ["dt", "vt"], ["fwd"]),
    "fwd_slow": ("Forward to slowing", ["fwd"], ["slow"]),
}


def _matlab_chars(dataset: h5py.Dataset) -> str:
    values = np.asarray(dataset[()]).ravel(order="F")
    return "".join(chr(int(value)) for value in values).strip()


def _matlab_string(file: h5py.File, ref) -> str:
    obj = file[ref]
    while isinstance(obj, h5py.Dataset) and obj.dtype == object:
        nested = np.asarray(obj[()]).ravel(order="F")
        if not len(nested):
            return ""
        obj = file[nested[0]]
    return _matlab_chars(obj)


def _normalize_neuron(name: str) -> str:
    # Kato uses zero-padded ventral/dorsal motor-neuron names (for example VB02).
    return re.sub(r"^([A-Z]+)0+(\d+)$", r"\1\2", name)


def _state_vector(group: h5py.Group) -> np.ndarray:
    matrix = np.column_stack([np.asarray(group[key][()]).ravel() for key in STATE_ORDER])
    return np.argmax(matrix, axis=1).astype(np.int64)


def read_kato() -> list[dict]:
    recordings = []
    with h5py.File(KATO, "r") as file:
        root = file["WT_NoStim"]
        name_refs = np.asarray(root["NeuronNames"][()]).ravel(order="F")
        trace_refs = np.asarray(root["deltaFOverF_bc"][()]).ravel(order="F")
        state_refs = np.asarray(root["States"][()]).ravel(order="F")
        time_refs = np.asarray(root["tv"][()]).ravel(order="F")
        dataset_refs = np.asarray(root["dataset"][()]).ravel(order="F")

        for index in range(len(trace_refs)):
            name_cells = file[name_refs[index]]
            names = [_matlab_string(file, ref) for ref in np.asarray(name_cells[()]).ravel(order="F")]
            traces = np.asarray(file[trace_refs[index]][()], dtype=float)
            times = np.asarray(file[time_refs[index]][()], dtype=float).ravel()
            states = _state_vector(file[state_refs[index]])
            if traces.shape[1] != len(states):
                size = min(traces.shape[1], len(states), len(times))
                traces, states, times = traces[:, :size], states[:size], times[:size]

            center = np.nanmean(traces, axis=1, keepdims=True)
            scale = np.nanstd(traces, axis=1, keepdims=True)
            scale[~np.isfinite(scale) | (scale == 0)] = 1
            z = (traces - center) / scale

            recordings.append(
                {
                    "id": index + 1,
                    "dataset": _matlab_string(file, dataset_refs[index]),
                    "names": names,
                    "traces": z,
                    "states": states,
                    "times": times,
                }
            )
    return recordings


def read_connectome() -> dict[str, dict]:
    data = loadmat(CONNECTOME, squeeze_me=True, struct_as_record=False)
    names = [str(value) for value in data["Neuron_ordered"]]
    chemical = data["A_init_t_ordered"].toarray().astype(float)
    electrical = data["Ag_t_ordered"].toarray().astype(float)
    strength = chemical.sum(axis=0) + chemical.sum(axis=1) + electrical.sum(axis=0) + electrical.sum(axis=1)
    order = np.argsort(np.argsort(strength))
    percentile = order / max(1, len(strength) - 1)
    return {
        name: {
            "strength": float(strength[i]),
            "percentile": float(percentile[i]),
            "chemical_in": float(chemical[:, i].sum()),
            "chemical_out": float(chemical[i, :].sum()),
            "gap": float((electrical[:, i].sum() + electrical[i, :].sum()) / 2),
        }
        for i, name in enumerate(names)
    }


def state_counts(recordings: list[dict]) -> dict:
    counts = Counter()
    transitions = Counter()
    for recording in recordings:
        states = recording["states"]
        counts.update(int(state) for state in states)
        for left, right in zip(states[:-1], states[1:]):
            if left != right:
                transitions[(int(left), int(right))] += 1
    return {
        "frames": {STATE_ORDER[i]: int(counts[i]) for i in range(len(STATE_ORDER))},
        "transitions": {
            f"{STATE_ORDER[left]}>{STATE_ORDER[right]}": int(value)
            for (left, right), value in transitions.items()
        },
    }


def candidate_tables(recordings: list[dict], connectome: dict[str, dict]) -> dict:
    output = {}
    for key, (label, source_states, target_states) in TRANSITIONS.items():
        source_idx = [STATE_ORDER.index(state) for state in source_states]
        target_idx = [STATE_ORDER.index(state) for state in target_states]
        rows = defaultdict(list)
        profiles = defaultdict(list)

        for recording in recordings:
            state = recording["states"]
            source_mask = np.isin(state, source_idx)
            target_mask = np.isin(state, target_idx)
            if source_mask.sum() < 10 or target_mask.sum() < 10:
                continue
            for neuron_index, raw_name in enumerate(recording["names"]):
                if not raw_name or raw_name.isdigit():
                    continue
                name = _normalize_neuron(raw_name)
                trace = recording["traces"][neuron_index]
                source_mean = float(np.nanmean(trace[source_mask]))
                target_mean = float(np.nanmean(trace[target_mask]))
                if not (math.isfinite(source_mean) and math.isfinite(target_mean)):
                    continue
                rows[name].append(
                    {
                        "recording": recording["id"],
                        "source": source_mean,
                        "target": target_mean,
                        "effect": target_mean - source_mean,
                    }
                )
                state_profile = []
                for state_index in range(len(STATE_ORDER)):
                    mask = state == state_index
                    state_profile.append(float(np.nanmean(trace[mask])) if mask.any() else None)
                profiles[name].append(state_profile)

        candidates = []
        for name, values in rows.items():
            if len(values) < 2 or name not in connectome:
                continue
            effects = np.asarray([row["effect"] for row in values])
            mean_effect = float(np.mean(effects))
            agreement = float(np.mean(np.sign(effects) == np.sign(mean_effect))) if mean_effect else 0.5
            profile_array = np.asarray(profiles[name], dtype=float)
            anatomy = connectome[name]
            candidates.append(
                {
                    "name": name,
                    "recordings": len(values),
                    "source": round(float(np.mean([row["source"] for row in values])), 4),
                    "target": round(float(np.mean([row["target"] for row in values])), 4),
                    "effect": round(mean_effect, 4),
                    "effect_se": round(float(np.std(effects, ddof=1) / math.sqrt(len(effects))) if len(effects) > 1 else 0, 4),
                    "agreement": round(agreement, 4),
                    "strength": round(anatomy["strength"], 1),
                    "anatomy_percentile": round(anatomy["percentile"], 4),
                    "chemical_in": round(anatomy["chemical_in"], 1),
                    "chemical_out": round(anatomy["chemical_out"], 1),
                    "gap": round(anatomy["gap"], 1),
                    "profile": [round(float(value), 4) for value in np.nanmean(profile_array, axis=0)],
                }
            )

        magnitudes = np.asarray([abs(row["effect"]) for row in candidates])
        magnitude_order = np.argsort(np.argsort(magnitudes)) if len(magnitudes) else np.array([])
        for index, row in enumerate(candidates):
            row["activity_percentile"] = round(float(magnitude_order[index] / max(1, len(candidates) - 1)), 4)
            row["reliability"] = round((row["recordings"] / len(recordings)) * row["agreement"], 4)
        candidates.sort(key=lambda row: (row["activity_percentile"] * 0.7 + row["anatomy_percentile"] * 0.3), reverse=True)
        output[key] = {
            "label": label,
            "source_states": source_states,
            "target_states": target_states,
            "candidates": candidates,
        }
    return output


class _Progress:
    def __init__(self, size, *args, **kwargs):
        self.size = size

    def __iter__(self):
        return iter(range(self.size))

    def set_postfix(self, *args, **kwargs):
        return None


def load_astera_cscg():
    # Execute the Astera-owned fork exactly, but allow a dependency-light pure-Python run.
    numba = types.ModuleType("numba")
    numba.njit = lambda function: function
    tqdm = types.ModuleType("tqdm")
    tqdm.trange = lambda size, *args, **kwargs: _Progress(size)
    sys.modules.setdefault("numba", numba)
    sys.modules.setdefault("tqdm", tqdm)
    sys.path.insert(0, str(ASTERA_CSCG))
    from chmm_actions import CHMM  # type: ignore

    return CHMM


def chmm_cross_validation(recordings: list[dict]) -> dict:
    CHMM = load_astera_cscg()
    results = {}
    for clone_count in (1, 2, 3):
        fold_scores = []
        for held_out in range(len(recordings)):
            sequences = [recording["states"].astype(np.int64) for recording in recordings]
            train_parts = [sequence for i, sequence in enumerate(sequences) if i != held_out]
            train_x = np.concatenate(train_parts)
            train_a = np.zeros(len(train_x), dtype=np.int64)
            cursor = 0
            for part in train_parts[:-1]:
                cursor += len(part)
                train_a[cursor - 1] = 1  # a separate boundary action avoids fake behavior transitions

            n_clones = np.repeat(clone_count, len(STATE_ORDER)).astype(np.int64)
            model = CHMM(n_clones, train_x, train_a, pseudocount=0.05, dtype=np.float64, seed=37 + held_out)
            model.learn_em_T(train_x, train_a, n_iter=10, term_early=False)
            test_x = sequences[held_out]
            test_a = np.zeros(len(test_x), dtype=np.int64)
            fold_scores.append(float(np.asarray(model.bps(test_x, test_a)).mean()))
        results[str(clone_count)] = {
            "mean_bps": round(float(np.mean(fold_scores)), 4),
            "sd_bps": round(float(np.std(fold_scores, ddof=1)), 4),
            "fold_bps": [round(value, 4) for value in fold_scores],
        }

    one = results["1"]["mean_bps"]
    best_key = min(results, key=lambda key: results[key]["mean_bps"])
    best = results[best_key]["mean_bps"]
    return {
        "models": results,
        "best_clones": int(best_key),
        "best_bps": best,
        "improvement_percent": round((one - best) / one * 100, 2),
    }


def main() -> None:
    recordings = read_kato()
    connectome = read_connectome()
    candidates = candidate_tables(recordings, connectome)
    frame_count = sum(len(recording["states"]) for recording in recordings)
    duration = sum(recording["times"][-1] - recording["times"][0] for recording in recordings)
    identified = []
    for recording in recordings:
        identified.extend(
            _normalize_neuron(name)
            for name in recording["names"]
            if name and not name.isdigit() and _normalize_neuron(name) in connectome
        )

    payload = {
        "meta": {
            "recordings": len(recordings),
            "frames": frame_count,
            "minutes": round(float(duration / 60), 1),
            "rois": int(sum(len(recording["names"]) for recording in recordings)),
            "identified_occurrences": len(identified),
            "unique_matched_neurons": len(set(identified)),
            "connectome_neurons": len(connectome),
            "state_labels": [STATE_LABELS[state] for state in STATE_ORDER],
        },
        "recordings": [
            {
                "id": recording["id"],
                "dataset": recording["dataset"],
                "frames": len(recording["states"]),
                "neurons": len(recording["names"]),
                "identified": sum(1 for name in recording["names"] if name and not name.isdigit()),
                "minutes": round(float((recording["times"][-1] - recording["times"][0]) / 60), 2),
            }
            for recording in recordings
        ],
        "state_counts": state_counts(recordings),
        "transitions": candidates,
        "chmm": chmm_cross_validation(recordings),
        "provenance": {
            "kato_osf": "https://osf.io/2395t/",
            "kato_file": "WT_NoStim.mat",
            "kato_sha256": "7531811c1718e26a0455f59cb2f8188cf25809278cfea85770dfe03315a0098a",
            "connectome_repo": "https://github.com/lrvarshney/elegans",
            "connectome_commit": "07d10c2d43b3da9a1fefed2e8658a98dc4310765",
            "astera_repo": "https://github.com/Astera-org/naturecomm_cscg",
            "astera_commit": "66c81ea061314d85dd305cfc7deced5b573296dd",
        },
    }
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    (ROOT / "data.js").write_text(f"window.ASTERA_DATA={serialized};\n", encoding="utf-8")
    (ROOT / "analysis" / "derived_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["meta"], indent=2))
    print(json.dumps(payload["chmm"], indent=2))
    for key, block in candidates.items():
        print(key, [(row["name"], row["effect"], row["recordings"], row["strength"]) for row in block["candidates"][:5]])


if __name__ == "__main__":
    main()
