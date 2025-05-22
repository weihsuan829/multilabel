import json
import os

# 載入外部 JSON（完整修復建議）
with open('damage_tips_full.json', encoding='utf-8') as f:
    damage_tips = json.load(f)