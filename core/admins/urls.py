from django.urls import path
from . import views 

app_name = 'admin_panel'

urlpatterns = [
    path('assignment_list/', views.assignment_list, name='assignment_list'),
    path('projects/', views.project_list, name='project_list'),
    path('create_project/', views.create_project, name='create_project'),
    path('assign_annotators/', views.assign_users, name='assign_annotators'),
    path('sentence_list/', views.sentence_list, name='sentence_list'),
    path('upload_sentences/', views.upload_sentences, name='upload_sentences'),
]