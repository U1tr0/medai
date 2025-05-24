from django.views.generic import ListView
from django.shortcuts import render, redirect
from .models import DicomStudy
from .forms import DicomUploadForm

class StudyListView(ListView):
    model = DicomStudy
    template_name = 'dicom_processor/study_list.html'
    context_object_name = 'studies'

def upload_study(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('study_list')
    else:
        form = DicomUploadForm()
    return render(request, 'dicom_processor/upload.html', {'form': form})