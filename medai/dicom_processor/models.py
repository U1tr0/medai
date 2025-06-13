from django.db import models
from django.core.files.base import ContentFile
import pydicom
from io import BytesIO
import os
import logging

logger = logging.getLogger(__name__)
class DicomStudy(models.Model):
    title = models.CharField(max_length=255, blank=True)
    dicom_file = models.FileField(upload_to='dicom_files/')
    patient_id = models.CharField(max_length=100, blank=True)
    patient_sex = models.CharField(max_length=10, blank=True)
    patient_age = models.IntegerField(null=True, blank=True)
    study_date = models.DateField(null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    study_instance_uid = models.CharField(max_length=100, blank=True)
    accession_number = models.CharField(max_length=100, blank=True)
    modality = models.CharField(max_length=20, blank=True)
    body_part_examined = models.CharField(max_length=100, blank=True)
    study_description = models.TextField(blank=True)
    original_patient_id = models.CharField(max_length=100, blank=True)  # Для анонимизированной версии
    original_patient_name = models.CharField(max_length=255, blank=True)  # Для анонимизированной версии

    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    result_left_hip = models.BooleanField(null=True, blank=True)  # True - перелом, False - норма
    result_right_hip = models.BooleanField(null=True, blank=True)
    dicom_preview = models.ImageField(
        upload_to='dicom_previews/',
        null=True,
        blank=True,
        verbose_name="DICOM Preview"
    )
    left_hip_image = models.ImageField(
        upload_to='processed/',
        null=True,
        blank=True
    )
    right_hip_image = models.ImageField(
        upload_to='processed/',
        null=True,
        blank=True
    )
    confidence_left = models.FloatField(null=True, blank=True, verbose_name="Confidence Score Left Hip")
    confidence_right = models.FloatField(null=True, blank=True, verbose_name="Confidence Score Right Hip")



    def preview_exists(self):
        return bool(self.dicom_preview) and os.path.exists(self.dicom_preview.path)

    def left_hip_exists(self):
        return bool(self.left_hip_image) and os.path.exists(self.left_hip_image.path)

    def right_hip_exists(self):
        return bool(self.right_hip_image) and os.path.exists(self.right_hip_image.path)
    def __str__(self):
        return f"Study {self.id} - {self.title}"

    def get_annotated_dicom(self):
        """Генерирует анонимизированный DICOM с результатами"""
        try:
            # Читаем оригинальный DICOM
            ds = pydicom.dcmread(self.dicom_file.path)

            # Анонимизация данных
            if 'PatientName' in ds:
                ds.PatientName = "Anonymous^Patient"
            if 'PatientID' in ds:
                ds.PatientID = self.patient_id

            # Добавляем результаты анализа (используем приватные теги)
            conclusion = f"""Результаты анализа MedAI:
            Left hip: {'Fracture' if self.result_left_hip else 'Normal'} (confidence: {self.confidence_left:.1f}%)
            Right hip: {'Fracture' if self.result_right_hip else 'Normal'} (confidence: {self.confidence_right:.1f}%)
            Conclusion: {'Pathology detected. You need to see a doctor' if self.result_left_hip or self.result_right_hip else 'No pathology detected'}
            Used model: ResNet18
            Service version: 1.0.0.
            """

            # Добавляем как приватные теги (0x0023 - зарезервировано для реализации)
            ds.add_new(0x00231010, 'LO', 'Processed by MedAI System')  # Private tag
            ds.StudyDescription = "Warning: For research purposes only. Purpose of the service: The service finds traces of hip fractures on X-ray images and provides a conclusion about their presence or absence."
            ds.ImageComments = conclusion
            ds.InstitutionName = "MedAI: Detection of hip fractures"

            # Сохраняем в буфер
            buffer = BytesIO()
            ds.save_as(buffer, write_like_original=False)
            buffer.seek(0)

            return ContentFile(buffer.getvalue(), name=f"result_{self.id}.dcm")

        except Exception as e:
            logger.error(f"Error generating annotated DICOM: {str(e)}", exc_info=True)
            return None