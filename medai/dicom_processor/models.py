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

    def __str__(self):
        return f"Study {self.id} - {self.title}"