from django.db import models
import os

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