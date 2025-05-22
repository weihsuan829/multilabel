import requests
import json
import re

def local_llm_summary(predictions, suggestions):
    if not predictions:
        return "未偵測到明顯損害，無需修復建議。"

    prompt = "你是一位紙本修復專家。這張檔案的受損狀況如下：\n"
    for p, s in zip(predictions, suggestions):
        prompt += f"- {p}：{s}\n"
    prompt += "請用繁體中文寫出完整總結，包括每項損害與保存建議。"

    try:
        response = requests.post("http://localhost:11434/api/generate",
                                 json={"model": "gemma:2b", "prompt": prompt},
                                 stream=True)
        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                result += data.get("response", "")
        return result.strip()
    except Exception as e:
        return f"⚠️ 呼叫本地模型時出錯：{e}"
