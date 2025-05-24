from django.contrib import admin
from .models import DicomStudy

@admin.register(DicomStudy)
class DicomStudyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'patient_id', 'processing_status', 'upload_date')