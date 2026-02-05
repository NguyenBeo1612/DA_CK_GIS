"""
URL configuration for TIEULUANCK_GIS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from main import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.index),
    path('login/', views.login),
    path('quanli/', views.quanli),
    path('vechungtoi/', views.vechungtoi),
    path('chuyencafe/', views.chuyencafe),


    path('danhmuc/list/', views.danhmuc_list),
    path('danhmuc/form/', views.danhmuc_form),

    path('thucdon/list/', views.thucdon_list),
    path('thucdon/form/', views.thucdon_form),

    path('khachhang/list/', views.khachhang_list),
    path('khachhang/form/', views.khachhang_form),

    path('nhanvien/list/', views.nhanvien_list),
    path('nhanvien/form/', views.nhanvien_form),

    path('donhang/list/', views.donhang_list),
    path('donhang/form/', views.donhang_form),

    path('chitiet/list/', views.chitiet_list),
    path('chitiet/form/', views.chitiet_form),

    path('chitiet/pay/', views.chitiet_pay),
    path('chitiet/pay-success/', views.chitiet_pay_success),
    path('chitiet/pay-error/', views.chitiet_pay_error),

    path('khuyenmai/list/', views.khuyenmai_list),
    path('khuyenmai/form/', views.khuyenmai_form),

    path('timkiem/', views.timkiem_result),
    path('Danhthu/', views.doanhthu),
    path('error/', views.error_page),
    path('chi_nhanh_gis/', views.chi_nhanh, name='chi_nhanh'),

    path('Giaodienkh/', views.Giaodienkh),
   # urls.py
    path('oder/', views.oder, name='order_page'),
]
