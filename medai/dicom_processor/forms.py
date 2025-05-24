from django import forms
from .models import DicomStudy

class DicomUploadForm(forms.ModelForm):
    class Meta:
        model = DicomStudy
        fields = ['title', 'dicom_file', 'patient_id', 'patient_sex', 'patient_age', 'study_date']