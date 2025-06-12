from django.views.generic import ListView, DetailView
from django.shortcuts import render, redirect
from .models import DicomStudy
from .forms import DicomUploadForm
import pydicom
from datetime import datetime
from .kafka_service import send_to_kafka
import hashlib
import logging

logger = logging.getLogger(__name__)


class StudyDetailView(DetailView):
    model = DicomStudy
    template_name = 'dicom_processor/dicomstudy_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_preview'] = bool(self.object.dicom_preview)
        return context


class StudyListView(ListView):
    model = DicomStudy
    template_name = 'dicom_processor/study_list.html'
    context_object_name = 'studies'
    ordering = ['-upload_date']
    paginate_by = 20


def anonymize_dicom_value(value):
    """Анонимизация значений с помощью хэширования"""
    if not value:
        return ''
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def extract_dicom_metadata(dicom_file):
    """Извлечение и анонимизация DICOM-метаданных"""
    try:
        ds = pydicom.dcmread(dicom_file)
        metadata = {
            # Анонимизированные данные
            'patient_id': anonymize_dicom_value(getattr(ds, 'PatientID', '')),
            'original_patient_id': getattr(ds, 'PatientID', ''),
            'original_patient_name': str(getattr(ds, 'PatientName', '')),

            # Медицинские метаданные
            'patient_sex': getattr(ds, 'PatientSex', ''),
            'patient_age': parse_dicom_age(getattr(ds, 'PatientAge', '')),
            'study_date': parse_dicom_date(getattr(ds, 'StudyDate', '')),
            'study_instance_uid': getattr(ds, 'StudyInstanceUID', ''),
            'accession_number': getattr(ds, 'AccessionNumber', ''),
            'modality': getattr(ds, 'Modality', ''),
            'body_part_examined': getattr(ds, 'BodyPartExamined', ''),
            'study_description': getattr(ds, 'StudyDescription', ''),
            'institution_name': getattr(ds, 'InstitutionName', ''),
        }
        return metadata
    except Exception as e:
        logger.error(f"Failed to extract DICOM metadata: {str(e)}")
        return {}


def parse_dicom_age(age_str):
    """Парсинг возраста из строки DICOM (формат '###Y')"""
    if not age_str:
        return None
    try:
        return int(age_str[:-1])  # Убираем последний символ (Y) и преобразуем в число
    except (ValueError, TypeError):
        return None


def parse_dicom_date(date_str):
    """Парсинг даты из строки DICOM (формат 'YYYYMMDD')"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        return None


def upload_study(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                study = form.save(commit=False)
                study.processing_status = 'pending'

                # Извлечение и обработка DICOM метаданных
                metadata = extract_dicom_metadata(request.FILES['dicom_file'])

                # Сохранение метаданных в модель
                study.patient_id = metadata.get('patient_id', '')
                study.patient_sex = metadata.get('patient_sex', '')
                study.patient_age = metadata.get('patient_age')
                study.study_date = metadata.get('study_date')
                study.study_instance_uid = metadata.get('study_instance_uid', '')
                study.accession_number = metadata.get('accession_number', '')
                study.modality = metadata.get('modality', '')
                study.body_part_examined = metadata.get('body_part_examined', '')
                study.study_description = metadata.get('study_description', '')
                study.original_patient_id = metadata.get('original_patient_id', '')
                study.original_patient_name = metadata.get('original_patient_name', '')

                study.save()

                # Отправка задачи в Kafka на обработку
                kafka_payload = {
                    'study_id': study.id,
                    'original_filename': request.FILES['dicom_file'].name,
                    'timestamp': datetime.now().isoformat(),
                }
                send_to_kafka('dicom_studies', kafka_payload)
                logger.info(f"Sent study {study.id} to Kafka for processing")

                return redirect('study_list')

            except Exception as e:
                logger.error(f"Failed to upload study: {str(e)}")
                form.add_error(None, f"Ошибка обработки DICOM-файла: {str(e)}")
    else:
        form = DicomUploadForm()

    return render(request, 'dicom_processor/upload.html', {
        'form': form,
        'max_upload_size': 50  # MB (можно вынести в настройки)
    })