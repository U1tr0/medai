from django.views.generic import ListView
from django.shortcuts import render, redirect
from .models import DicomStudy
from .forms import DicomUploadForm
import pydicom
from datetime import datetime
from .kafka_service import send_to_kafka
from django.views.generic import DetailView
from .models import DicomStudy


class StudyDetailView(DetailView):
    model = DicomStudy

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_preview'] = bool(self.object.dicom_preview)
        return context

class StudyListView(ListView):
    model = DicomStudy
    template_name = 'dicom_processor/study_list.html'
    context_object_name = 'studies'


def upload_study(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            study = form.save(commit=False)

            # Чтение DICOM-файла
            dicom_file = request.FILES['dicom_file']
            ds = pydicom.dcmread(dicom_file)

            # Извлечение метаданных
            study.patient_id = getattr(ds, 'PatientID', '')
            study.patient_sex = getattr(ds, 'PatientSex', '')
            study.patient_age = getattr(ds, 'PatientAge', '')[:3] if hasattr(ds, 'PatientAge') else None
            study.study_date = datetime.strptime(ds.StudyDate, '%Y%m%d').date() if hasattr(ds, 'StudyDate') else None

            study.save()

            # Отправка в Kafka (позже добавим модель)
            print(f"!!! Отправляю в Kafka study_id={study.id}")
            send_to_kafka('dicom_studies', {'study_id': study.id})

            return redirect('study_list')
    else:
        form = DicomUploadForm()
    return render(request, 'dicom_processor/upload.html', {'form': form})