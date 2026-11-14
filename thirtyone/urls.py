from django.urls import path
from game import views

urlpatterns = [path('', views.home), path('create/', views.create), path('join/', views.join), path('room/<str:code>/', views.room), path('room/<str:code>/state/', views.state), path('room/<str:code>/action/', views.action)]
