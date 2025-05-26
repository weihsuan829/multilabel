
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
from model_mac import load_model, predict as predict_labels
import requests
import json
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

model = load_model()

with open('damage_tips.json', encoding='utf-8') as f:
    damage_tips = json.load(f)
# damage_tips = {
#     "變色泛黃": "避免陽光直射，使用無酸保存紙材儲存。",
#     "黴斑（黃斑、褐斑）": "可使用酒精棉輕拭或冷凍處理防霉，環境應保持通風乾燥。",
#     "皺褶痕": "可使用壓重板或低溫濕壓展平，避免高溫熨燙造成損傷。",
#     "紙張裂痕": "建議使用日本紙與中性膠背貼修復，避免直接使用膠帶。",
#     "孔洞": "可用修補紙張填補背襯，必要時使用手工黏合強化脆弱區域。",
#     "金屬鏽痕": "使用還原劑去除鏽斑，並避免接觸含鐵金屬及高濕環境。",
#     "膠帶膠痕": "應以低溫熱風或專業溶劑除膠，避免用手撕除造成額外破壞。",
#     "水漬痕": "以風乾方式處理並置於低濕環境中，避免霉菌滋生。",
#     "油墨污漬": "避免擦拭擴散，可考慮使用固定劑處理墨水邊界。",
#     "髒污": "使用刷子或橡皮擦清潔，避免使用濕布導致染色或損傷。"
# }

def to_chinese_numeral(n):
    numerals = "一二三四五六七八九十"
    if 1 <= n <= 10:
        return numerals[n - 1]
    return str(n)

def format_llm_output(text):
    text = text.replace("**", "").replace("--", "-").strip()
    text = re.sub(r"文件受損狀況及保存建議[:：]?", "", text, flags=re.IGNORECASE)

    # output = ["檔案受損情況總結：本檔案包含以下損害，建議採用下列修復方式。\n"]
    output = ["檔案受損情況總結："]
    damage_keywords = ["皺褶痕", "黴斑", "髒污", "孔洞", "變色泛黃", "油墨污漬", "膠帶膠痕", "水漬痕", "金屬鏽痕", "紙張裂痕"]

    keyword_index = 1
    lines = text.splitlines()
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        matched = next((kw for kw in damage_keywords if kw in line), None)
        if matched:
            formatted_lines.append(f"{to_chinese_numeral(keyword_index)}、{matched}")
            keyword_index += 1
            continue
        if not formatted_lines and not line.startswith("-"):
            formatted_lines.append(line)
            continue
        if not line.startswith("-"):
            line = "- " + line
        formatted_lines.append(line)

    spaced_lines = []
    for line in formatted_lines:
        spaced_lines.append(line)
        if re.match(r"^(- )?[一二三四五六七八九十]、", line):
            continue
        if line.startswith("-"):
            continue
        spaced_lines.append("")
    output.extend(spaced_lines)
    return "\n".join(output).strip()

def local_llm_summary(predictions, suggestions):
    if not predictions:
        return "未偵測到明顯損害，無需修復建議。"

    prompt = "你是一位紙本修復專家。這張檔案的受損狀況如下：\n"
    

    for p, s in zip(predictions, suggestions):
        prompt += f"- {p}：{s}\n"
    prompt += "請你用繁體中文寫一段不超過 100 字的簡潔說明，總結這份檔案的損害情況與建議。請以完整段落回應，**不需條列、不需換行、不需標題**。"

    try:
        print("[DEBUG] 發送 prompt 給 Ollama...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "tinyllama:latest", "prompt": prompt},
            stream=True
        )

        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                result += data.get("response", "")

        # cleaned = result.strip()
        # formatted = format_llm_output(cleaned)
        return result.strip() if result.strip() else "⚠️ 模型沒有產生回應，請稍後再試。"

    except Exception as e:
        print("[ERROR] 呼叫 LLM 發生例外：", e)
        return f"⚠️ 呼叫本地模型時出錯：{e}"

def clean_markdown(text):
    # 移除粗體與斜體符號，例如 **文字**、*文字*
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # 移除開頭的破折號 + 空白（像是 "- 修復建議：..."）
    text = re.sub(r'^\s*-\s*', '', text, flags=re.MULTILINE)
    return text.strip()


def save_image(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filename, filepath

def predict_damage_labels(image_path):
    prediction = predict_labels(model, image_path)
    suggestions = [f"{p}：{damage_tips.get(p, '無建議')}" for p in prediction]
    return prediction, suggestions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'image' not in request.files:
        return redirect(url_for('index'))

    file = request.files['image']
    if file.filename == '':
        return redirect(url_for('index'))

    filename, filepath = save_image(file)

    prediction, suggestions = predict_damage_labels(filepath)

    return render_template('index.html',
                           image_path=url_for('static', filename='uploads/' + filename),
                           prediction=prediction,
                           suggestions=suggestions,
                           gpt=False)


@app.route('/gpt', methods=['POST'])
def gpt_analysis():
    if 'image' not in request.files:
        return redirect(url_for('index'))

    file = request.files['image']
    if file.filename == '':
        return redirect(url_for('index'))

    # 儲存上傳的圖片
    filename, filepath = save_image(file)

    # 執行模型預測
    prediction, suggestions = predict_damage_labels(filepath)

    # 呼叫 GPT 模型生成說明文字
    summary = local_llm_summary(prediction, suggestions)

    return render_template('index.html',
                           image_path=url_for('static', filename='uploads/' + filename),
                           prediction=prediction,
                           suggestions=suggestions,
                           summary=summary,
                           gpt=True)  # ✅ gpt=True 讓模板切換顯示邏輯


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    if not message:
        return jsonify({'reply': '⚠️ 請輸入內容。'})

    # 使用 GPT 本地或 API 回應
    try:
        prompt = f"使用者提問：{message}\n請用繁體中文回答。"
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma:2b", "prompt": prompt},
            stream=True
        )
        reply = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                reply += data.get("response", "")
        return jsonify({'reply': clean_markdown(reply)})
    except Exception as e:
        return jsonify({'reply': f"⚠️ 回應錯誤：{e}"})


if __name__ == '__main__':
    app.run(debug=True)
