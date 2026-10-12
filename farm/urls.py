from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('block/<int:block_number>/', views.block_detail, name='block_detail'),
    path('block/<int:block_number>/history/', views.block_history, name='block_history'), 
]