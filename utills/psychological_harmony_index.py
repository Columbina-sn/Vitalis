# utills/psychological_harmony_index.py
"""
心理和谐指数（Psychological Harmony Index, PHI）计算模块。

优化版 v2 计算逻辑：
1. 计算每个维度相对于理想值的对称偏差率，转化为 0~1 的和谐贡献度。
2. 计算贡献度的算术平均作为基础指数。
3. 检测情绪基调与自我价值两个“污染源”，超出阈值时施加额外折扣。
4. 引入短板惩罚系数：若最小贡献度低于 0.5，对基础指数施加温和折扣，
   避免调和平均式的一票否决，同时保持对严重短板的敏感性。
5. 最终映射到 0-100 整数指数。
"""
from typing import Union


def calculate_phi(
    physical_vitality: Union[int, float],
    emotional_tone: Union[int, float],
    relationship_connection: Union[int, float],
    self_worth: Union[int, float],
    meaning_direction: Union[int, float],
) -> int:
    """
    计算心理和谐指数。

    Args:
        physical_vitality: 身心活力 (1-100)
        emotional_tone: 情绪基调 (1-100)
        relationship_connection: 关系联结 (1-100)
        self_worth: 自我价值 (1-100)
        meaning_direction: 意义方向 (1-100)

    Returns:
        心理和谐指数 (0-100 的整数)
    """
    # 理想平衡点
    ideal = {
        "physical": 80,
        "emotional": 75,
        "relation": 80,
        "worth": 85,
        "meaning": 75,
    }

    def _contribution(score: float, ideal_val: float) -> float:
        """计算单个维度的和谐贡献度（0~1），对称偏差处理。"""
        if score >= ideal_val:
            if ideal_val == 100:
                dev = 0.0
            else:
                dev = (score - ideal_val) / (100 - ideal_val)
        else:
            if ideal_val == 0:
                dev = 0.0
            else:
                dev = (ideal_val - score) / ideal_val
        return max(0.0, min(1.0, 1.0 - dev))

    contributions = [
        _contribution(physical_vitality, ideal["physical"]),
        _contribution(emotional_tone, ideal["emotional"]),
        _contribution(relationship_connection, ideal["relation"]),
        _contribution(self_worth, ideal["worth"]),
        _contribution(meaning_direction, ideal["meaning"]),
    ]

    # 算术平均作为基础和谐度
    base_index = sum(contributions) / len(contributions) * 100.0

    # 短板惩罚：取最小贡献度，若低于0.5则施加折扣（0.5~1.0）
    min_contrib = min(contributions)
    if min_contrib < 0.5:
        penalty = 0.5 + 0.5 * (min_contrib / 0.5)  # 线性映射：贡献度0 -> 0.5，贡献度0.5 -> 1.0
    else:
        penalty = 1.0

    raw_index = base_index * penalty

    # 污染折扣：情绪或自我价值极端时，整体再打八折
    discount = 1.0
    if emotional_tone < 30 or emotional_tone > 95:
        discount *= 0.8
    if self_worth < 30 or self_worth > 95:
        discount *= 0.8

    phi = raw_index * discount

    # 取整并限制在0-100
    phi = max(0, min(100, int(round(phi))))
    return phi