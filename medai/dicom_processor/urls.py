from django.urls import path
from . import views
from .views import StudyDetailView
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('', views.StudyListView.as_view(), name='study_list'),
    path('upload/', views.upload_study, name='upload_study'),
    path('study/<int:pk>/', StudyDetailView.as_view(), name='study_detail'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)