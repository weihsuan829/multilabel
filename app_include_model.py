import os
from flask import Flask, render_template, request
from model_mac import load_model, predict
import requests  # 用於呼叫 Ollama API
import json

app = Flask(__name__)

# 載入模型
model = load_model()

# LLM 模型名稱（可改為 "qwen:7b", "mistral", "phi", 等）
LLM_MODEL = "gemma:2b"

# 修復建議字典
damage_tips = {
    "變色泛黃": "避免陽光直射，使用無酸保存紙材儲存。",
    "黴斑（黃斑、褐斑）": "可使用酒精棉輕拭或冷凍處理防霉，環境應保持通風乾燥。",
    "皺褶痕": "可使用壓重板或低溫濕壓展平，避免高溫熨燙造成損傷。",
    "紙張裂痕": "建議使用日本紙與中性膠背貼修復，避免直接使用膠帶。",
    "孔洞": "可用修補紙張填補背襯，必要時使用手工黏合強化脆弱區域。",
    "金屬鏽痕": "使用還原劑去除鏽斑，並避免接觸含鐵金屬及高濕環境。",
    "膠帶膠痕": "應以低溫熱風或專業溶劑除膠，避免用手撕除造成額外破壞。",
    "水漬痕": "以風乾方式處理並置於低濕環境中，避免霉菌滋生。",
    "油墨污漬": "避免擦拭擴散，可考慮使用固定劑處理墨水邊界。",
    "髒污": "使用刷子或橡皮擦清潔，避免使用濕布導致染色或損傷。"
}

import re

# 格式處理函式：將 LLM 輸出文字轉為結構清楚的內容
def format_llm_output(text):
    import re

    # 清除 Markdown 與雜項符號
    text = text.replace("**", "").replace("--", "-").strip()
    text = re.sub(r"文件受損狀況及保存建議[:：]?", "", text, flags=re.IGNORECASE)

    # 設定自訂標題開頭
    output = [
        
        "檔案受損情況總結：本檔案包含以下損害，建議採用下列修復方式。\n"
    ]

    # 定義可識別的損壞類型 → 自動加條列序號
    damage_keywords = ["皺褶痕", "黴斑", "髒污", "孔洞", "變色泛黃", "油墨污漬", "膠帶膠痕", "水漬痕", "金屬鏽痕", "紙張裂痕"]
    keyword_index = 1

    lines = text.splitlines()
    current_section = ""
    formatted_lines = []

    for line in lines:
        line = line.strip()

        if not line:
            continue  # 跳過空行

        # 偵測修復類型開頭（例如：皺褶痕）
        matched = next((kw for kw in damage_keywords if kw in line), None)
        if matched:
            # 新段落：加上條列序號＋粗體（後端呈現為純文字）
            formatted_lines.append(f"{to_chinese_numeral(keyword_index)}、{matched}")
            keyword_index += 1
            continue

        # 其他條列建議
        # 第一行為總結語，不加條列符號
        if not formatted_lines and not line.startswith("-"):
            formatted_lines.append(line)
            continue

        # 其他行補上條列符號
        if not line.startswith("-"):
            line = "- " + line

        formatted_lines.append(line)

    # 每段後補空行
    spaced_lines = []
    for line in formatted_lines:
        spaced_lines.append(line)
        if re.match(r"^(- )?[一二三四五六七八九十]、", line):
            continue  # 標題本身不加空行
        if line.startswith("-"):
            continue
        spaced_lines.append("")

    output.extend(spaced_lines)
    return "\n".join(output).strip()


# 輔助：將 1,2,3 轉為 一、二、三...
def to_chinese_numeral(n):
    numerals = "一二三四五六七八九十"
    if 1 <= n <= 10:
        return numerals[n - 1]
    return str(n)




# 本地 LLM 整合：呼叫 Ollama 模型並格式化結果
def local_llm_summary(prediction_list, suggestion_list):
    if not prediction_list:
        return "未偵測到明顯損害，無需修復建議。"

    # 🔧 組 prompt 給模型
    prompt = "你是一位紙本修復專家。這張檔案的受損狀況如下：\n"
    for p, s in zip(prediction_list, suggestion_list):
        prompt += f"- {p}：{s}\n"
    prompt += "請用繁體中文寫出完整總結，包括每項損害與保存建議。"

    try:
        print("[DEBUG] 發送 prompt 給 Ollama...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma:2b", "prompt": prompt},
            stream=True
        )

        # Step 1：串流接收模型回應
        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                result += data.get("response", "")

        # Step 2：格式化回應
        cleaned = result.strip()
        formatted = format_llm_output(cleaned)
        return formatted if formatted else "⚠️ 模型沒有產生回應，請稍後再試。"

    except Exception as e:
        print("[ERROR] 呼叫 LLM 發生例外：", e)
        return f"⚠️ 呼叫本地模型時出錯：{e}"

@app.route("/", methods=["GET", "POST"])
def index():
    prediction = []
    suggestions = []
    image_path = None
    summary = None  # 確保 summary 在 GET 狀態下也有定義

    if request.method == "POST":
        file = request.files.get("image")
        if file and file.filename != "":
            # 建立儲存資料夾
            upload_folder = "static/uploads"
            os.makedirs(upload_folder, exist_ok=True)

            # 儲存圖片
            image_path = os.path.join(upload_folder, file.filename)
            file.save(image_path)

            # 模型預測
            prediction = predict(model, image_path)

            # 對應建議
            # suggestions = [damage_tips.get(p, "無建議") for p in prediction]
            suggestions = [f"{p}：{damage_tips.get(p, '無建議')}" for p in prediction]
            # unique_predictions = list(dict.fromkeys(prediction))  # ✅ 保留順序且去重複
            # suggestions = [damage_tips.get(p, "無建議") for p in unique_predictions]

            # LLM產生的整體修復說明（額外補充，不取代 suggestions）
            summary = local_llm_summary(prediction, suggestions)

    return render_template("index.html",
                           image_path=image_path,
                           prediction=prediction,
                           suggestions=suggestions,
                           summary=summary)

if __name__ == "__main__":
    app.run(debug=True)
