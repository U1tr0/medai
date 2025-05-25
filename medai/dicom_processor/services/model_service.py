import torch
import torch.nn as nn
from torchvision import transforms
import cv2
import numpy as np
from PIL import Image
import pydicom


class HipFractureDetector:
    def __init__(self, model_path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.load_model(model_path)
        self.transform = transforms.Compose([
            transforms.Resize((416, 416)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                  [0.229, 0.224, 0.225])
        ])

    def load_model(self, path):
        model = torch.load(path, map_location=self.device)
        model.eval()
        return model

    def preprocess_dicom(self, dicom_path):
        """Разделяет DICOM на два сустава и предобрабатывает"""
        ds = pydicom.dcmread(dicom_path)
        img = ds.pixel_array.astype(np.float32)

        # Нормализация
        img = (img - img.min()) / (img.max() - img.min()) * 255
        img = img.astype(np.uint8)

        # Разделение на левую и правую половины
        height, width = img.shape
        left_img = img[:, :width // 2]
        right_img = img[:, width // 2:]

        return left_img, right_img

    def predict(self, image):
        """Предсказание для одного сустава"""
        image = Image.fromarray(image).convert('L')  # В grayscale
        image = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.model(image)
            prob = torch.sigmoid(output).item()

        return prob > 0.5  # True если перелом