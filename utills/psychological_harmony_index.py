# utills/psychological_harmony_index.py
"""
心理和谐指数（Psychological Harmony Index, PHI）计算模块。

输入五个心理维度分数（1-100），输出一个0-100的综合指数，
分数越高表示内在状态越和谐。

计算逻辑：
1. 计算各维度相对于理想值的百分比偏差。
2. 检测情绪基调与自我价值两个“污染源”，若超出阈值则产生污染系数。
3. 污染系数会放大关系联结与意义方向两个维度的偏差权重。
4. 加权平均后映射到0-100指数。
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

    # 1. 百分比偏差
    dev = {
        "physical": abs(physical_vitality - ideal["physical"]) / ideal["physical"],
        "emotional": abs(emotional_tone - ideal["emotional"]) / ideal["emotional"],
        "relation": abs(relationship_connection - ideal["relation"]) / ideal["relation"],
        "worth": abs(self_worth - ideal["worth"]) / ideal["worth"],
        "meaning": abs(meaning_direction - ideal["meaning"]) / ideal["meaning"],
    }

    # 2. 污染源检测
    # 情绪污染系数
    if emotional_tone < 30 or emotional_tone > 95:
        coeff_emo = 1 + (abs(emotional_tone - 75) / 75)
    else:
        coeff_emo = 1.0

    # 自我污染系数
    if self_worth < 30 or self_worth > 95:
        coeff_worth = 1 + (abs(self_worth - 85) / 85)
    else:
        coeff_worth = 1.0

    # 3. 放大权重
    w_relation = coeff_emo * coeff_worth
    w_meaning = coeff_emo * coeff_worth

    # 4. 加权平均偏差
    weighted_sum = (
        dev["physical"] * 1
        + dev["emotional"] * 1
        + dev["relation"] * w_relation
        + dev["worth"] * 1
        + dev["meaning"] * w_meaning
    )
    weight_total = 1 + 1 + w_relation + 1 + w_meaning  # = 5 + (w_rel-1) + (w_mean-1)

    weighted_avg_dev = weighted_sum / weight_total

    # 5. 最终指数
    phi = (1 - weighted_avg_dev) * 100

    # 限制在0-100，取整
    phi = max(0, min(100, int(round(phi))))
    return phi