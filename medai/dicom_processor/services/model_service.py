import torch
import torch.nn as nn
from torchvision import models, transforms
import pydicom
import numpy as np
from PIL import Image
import logging
import os

logger = logging.getLogger(__name__)


class HipFractureDetector:
    def __init__(self, model_path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.load_model(model_path)
        self.transform = self.get_transforms()
        logger.info("HipFractureDetector initialized successfully")

    def load_model(self, model_path):
        """Загрузка модели с предварительно обученными весами"""
        try:
            model = models.resnet18(weights=None)
            model.fc = nn.Linear(model.fc.in_features, 2)  # 2 класса

            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at {model_path}")

            state_dict = torch.load(model_path, map_location=self.device)
            model.load_state_dict(state_dict)

            model.eval()
            model.to(self.device)

            logger.info(f"Model loaded successfully from {model_path}")
            return model

        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    def get_transforms(self):
        """Преобразования для изображений"""
        return transforms.Compose([
            transforms.Resize((416, 416)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])

    def dicom_to_rgb(self, dicom_path):
        """Конвертация DICOM в 3-канальное RGB изображение"""
        try:
            ds = pydicom.dcmread(dicom_path)
            img = ds.pixel_array.astype(np.float32)
            img = (img - img.min()) / (img.max() - img.min()) * 255
            img = img.astype(np.uint8)
            pil_img = Image.fromarray(img).convert('L')
            rgb_img = Image.merge("RGB", (pil_img, pil_img, pil_img))
            return rgb_img

        except Exception as e:
            logger.error(f"DICOM to RGB conversion failed: {str(e)}")
            raise

    def preprocess_dicom(self, dicom_path):
        """Обработка DICOM файла и разделение на суставы"""
        try:
            img = self.dicom_to_rgb(dicom_path)
            width, height = img.size
            left_img = img.crop((0, 0, width // 2, height))
            right_img = img.crop((width // 2, 0, width, height))
            return left_img, right_img

        except Exception as e:
            logger.error(f"DICOM preprocessing failed: {str(e)}")
            raise

    def predict_with_confidence(self, image_pil):
        """Предсказание с возвратом confidence score"""
        try:
            image = self.transform(image_pil).unsqueeze(0).to(self.device)

            with torch.no_grad():
                outputs = self.model(image)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                confidence, preds = torch.max(probabilities, 1)

            return bool(preds.item()), confidence.item()

        except Exception as e:
            logger.error(f"Prediction with confidence failed: {str(e)}")
            raise

    def predict(self, image_pil):
        """Предсказание для PIL Image (совместимость)"""
        pred, _ = self.predict_with_confidence(image_pil)
        return pred

    def process_dicom(self, dicom_path):
        try:
            left_img, right_img = self.preprocess_dicom(dicom_path)

            left_pred, left_confidence = self.predict_with_confidence(left_img)
            right_pred, right_confidence = self.predict_with_confidence(right_img)

            # Преобразование confidence в проценты
            left_confidence = left_confidence * 100
            right_confidence = right_confidence * 100

            logger.info(
                f"Processed DICOM: Left {'Fracture' if left_pred else 'Normal'} "
                f"({left_confidence:.1f}%), Right {'Fracture' if right_pred else 'Normal'} "
                f"({right_confidence:.1f}%)"
            )

            return left_pred, left_confidence, right_pred, right_confidence

        except Exception as e:
            logger.error(f"Full processing failed: {str(e)}", exc_info=True)
            raise