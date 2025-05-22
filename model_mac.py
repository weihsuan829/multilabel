import torch
from torchvision import transforms
from PIL import Image
import numpy as np
from model_choose_v3 import model_choose



import torch
from torchvision import transforms
from PIL import Image
from model_choose_v3 import model_choose

device = torch.device("cpu")
model_path = 'fold3.pth'
labels = ['金屬鏽痕', '油墨污漬', '變色泛黃', '孔洞', '水漬痕', '膠帶膠痕', '皺褶痕', '紙張裂痕', '黴斑（黃斑、褐斑）', '髒污']

def load_model():
    model = model_choose('densenet', num_labels=len(labels))
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    return model

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5]*3, [0.5]*3)
])

def predict(model, image_path):
    image = Image.open(image_path).convert("RGB")
    image_tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        outputs = model(image_tensor)
        probs = torch.sigmoid(outputs).squeeze().cpu().numpy()
        results = [labels[i] for i, p in enumerate(probs) if p > 0.5]
    return results

