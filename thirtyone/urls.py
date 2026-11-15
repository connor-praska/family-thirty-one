from django.urls import path
from game import views

urlpatterns = [path('', views.home), path('create/', views.create), path('join/', views.join), path('room/<str:code>/', views.room), path('room/<str:code>/state/', views.state), path('room/<str:code>/action/', views.action)]
urlpatterns += [path('room/<str:code>/chat/', views.chat)]
urlpatterns += [path('games/31/', views.thirtyone, name='thirtyone')]
urlpatterns += [path('games/pinochle/', views.pinochle_home, name='pinochle'),
                path('games/pinochle/create/', views.create, {'game_type': 'pinochle'})]
