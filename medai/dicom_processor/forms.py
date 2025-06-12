from django import forms
from django.core.exceptions import ValidationError
from .models import DicomStudy
import os


class DicomUploadForm(forms.ModelForm):
    class Meta:
        model = DicomStudy
        fields = ['title', 'dicom_file']

    def clean_dicom_file(self):
        dicom_file = self.cleaned_data.get('dicom_file')

        # Проверка расширения файла
        ext = os.path.splitext(dicom_file.name)[1].lower()
        if ext not in ['.dcm', '.dicom']:
            raise ValidationError("Файл должен быть в формате DICOM (.dcm или .dicom)")

        return dicom_file