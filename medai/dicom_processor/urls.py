from django.urls import path
from . import views

urlpatterns = [
    path('', views.StudyListView.as_view(), name='study_list'),
    path('upload/', views.upload_study, name='upload_study'),
]