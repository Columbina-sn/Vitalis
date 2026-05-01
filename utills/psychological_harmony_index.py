# utils/psychological_harmony_index.py
"""
心理和谐指数（Psychological Harmony Index, PHI）计算模块
采用均方根偏差法（RMSD），对短板的惩罚更真实、敏锐。
"""
import math
from typing import Union


def calculate_phi(
        physical_vitality: Union[int, float],
        emotional_tone: Union[int, float],
        relationship_connection: Union[int, float],
        self_worth: Union[int, float],
        meaning_direction: Union[int, float],
) -> int:
    ideal = {
        "physical": 80,
        "emotional": 75,
        "relation": 80,
        "worth": 85,
        "meaning": 75,
    }

    def dev(score: float, ideal_val: float) -> float:
        if score >= ideal_val:
            if ideal_val == 100:
                return 0.0
            return (score - ideal_val) / (100 - ideal_val)
        else:
            if ideal_val == 0:
                return 0.0
            return (ideal_val - score) / ideal_val

    devs = [
        dev(physical_vitality, ideal["physical"]),
        dev(emotional_tone, ideal["emotional"]),
        dev(relationship_connection, ideal["relation"]),
        dev(self_worth, ideal["worth"]),
        dev(meaning_direction, ideal["meaning"]),
    ]

    # 均方根偏差
    rmsd = math.sqrt(sum(d ** 2 for d in devs) / len(devs))

    # 可选的灵敏度缩放：默认1.0，若想一个0正好50分，可改为1.118
    scale = 1.0
    phi = (1 - min(rmsd * scale, 1.0)) * 100
    return max(0, min(100, round(phi)))