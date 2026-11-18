import numpy as np
from .science import utility, metrics


def fixed_question(bank):
    group = bank.lookup["N5/R041"]
    indices = [int(np.argmin(abs(bank.temperatures - t))) for t in [22.0, 23.0]]
    if indices[0] == indices[1]:
        indices = [0, len(bank.temperatures) - 1]
    a, b = sorted(indices)
    return dict(
        id=f'{group["id"]}:{a}:{b}',
        group_id=group["id"],
        grid=group["grid"],
        a=a,
        b=b,
        source_version=bank.version,
        selection_method="fixed_intro_v2",
        exact_discrete_global=False,
        eig_bits=None,
    )


def present(bank, question, seed, trial_count):
    q = dict(question)
    g = bank.lookup[q["group_id"]]
    t = bank.temperatures[[q["a"], q["b"]]]
    u = utility(t, g["desired"], bank.settings)
    differences = np.abs(t[:, None] - np.array(g["desired"])[None, :])
    q.update(
        presentation_version="scenario-distance-demographics-v2",
        desired=g["desired"],
        temperatures=t.tolist(),
        utilities=u.tolist(),
        metrics={k: v.tolist() for k, v in metrics(u).items()},
        temperature_difference=dict(
            mean_c=differences.mean(axis=1).tolist(),
            worst_c=differences.max(axis=1).tolist(),
            individual_c=differences.tolist(),
        ),
        participants=[
            dict(label=f"참여자 {i+1}", **bank.people[person])
            for i, person in enumerate(g["members"])
        ],
        scenario=dict(
            n=g["n"],
            desired_min_c=min(g["desired"]),
            desired_max_c=max(g["desired"]),
            description=f'연구 참여자의 자료를 재조합한 가상 {g["n"]}명이 한 공간에서 같은 설정 온도를 사용한다고 가정합니다. 각자의 희망 온도가 다른 상황에서 두 안 중 하나를 선택해 주세요.',
            provenance="실제 동시 재실 집단이 아닌 합성 그룹입니다. 성별·나이는 원자료, 희망 온도는 연구에서 도출한 대표값입니다.",
        ),
        display_seed=seed + trial_count,
        display_order=np.random.default_rng(seed + trial_count).permutation(2).tolist(),
        label="어떤 공유 온도를 선택하시겠어요?",
        utility_interpretation="모델 효용: 실제 쾌적감 측정값이 아닙니다.",
    )
    return q
