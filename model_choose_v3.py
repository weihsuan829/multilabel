import torchvision
import torch.nn as nn
from torchvision.models import DenseNet201_Weights, ViT_B_16_Weights, Swin_V2_B_Weights, ResNet50_Weights

def model_choose(model_name: str, num_labels: int, pretrain: bool = False, fine_tune: bool = True):
    def vit_model(num_labels: int, pretrain: bool):
        weights = ViT_B_16_Weights.IMAGENET1K_V1 if pretrain else None
        model = torchvision.models.vit_b_16(weights=weights)
        if not fine_tune:
            for param in model.parameters():
                param.requires_grad = False
        model.heads = nn.Linear(in_features=768, out_features=num_labels)
        return model

    def swin_model(num_labels: int, pretrain: bool):
        weights = Swin_V2_B_Weights.IMAGENET1K_V1 if pretrain else None
        model = torchvision.models.swin_v2_b(weights=weights)
        if not fine_tune:
            for param in model.parameters():
                param.requires_grad = False
        model.head = nn.Linear(in_features=1024, out_features=num_labels)
        return model

    def densenet201(num_labels: int, pretrain: bool):
        weights = DenseNet201_Weights.IMAGENET1K_V1 if pretrain else None
        model = torchvision.models.densenet201(weights=weights)
        if not fine_tune:
            for param in model.parameters():
                param.requires_grad = False
        model.classifier = nn.Linear(in_features=1920, out_features=num_labels)
        return model

    def resnet50(num_labels: int, pretrain: bool):
        weights = ResNet50_Weights.IMAGENET1K_V1 if pretrain else None
        model = torchvision.models.resnet50(weights=weights)
        if not fine_tune:
            for param in model.parameters():
                param.requires_grad = False
        model.fc = nn.Linear(in_features=model.fc.in_features, out_features=num_labels)
        return model

    # 模型選擇
    if model_name == "vit":
        model = vit_model(num_labels, pretrain)
    elif model_name == "swin_vit":
        model = swin_model(num_labels, pretrain)
    elif model_name == "densenet":
        model = densenet201(num_labels, pretrain)
    elif model_name == "resnet":
        model = resnet50(num_labels, pretrain)
    else:
        raise ValueError(f"未知的模型名稱: {model_name}，請使用 'densenet', 'vit', 'swin_vit' 或 'resnet'。")

    return model
