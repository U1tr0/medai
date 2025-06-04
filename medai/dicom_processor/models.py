from django.db import models

class DicomStudy(models.Model):
    title = models.CharField(max_length=255, blank=True)
    dicom_file = models.FileField(upload_to='dicom_files/')
    patient_id = models.CharField(max_length=100, blank=True)
    patient_sex = models.CharField(max_length=10, blank=True)
    patient_age = models.IntegerField(null=True, blank=True)
    study_date = models.DateField(null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
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

    def preview_exists(self):
        return bool(self.dicom_preview) and os.path.exists(self.dicom_preview.path)

    def left_hip_exists(self):
        return bool(self.left_hip_image) and os.path.exists(self.left_hip_image.path)

    def right_hip_exists(self):
        return bool(self.right_hip_image) and os.path.exists(self.right_hip_image.path)
    def __str__(self):
        return f"Study {self.id} - {self.title}"