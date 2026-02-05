from django.shortcuts import render

# Create your views here.

def index(request):
    return render(request, 'index1.html')

def login(request):
    return render(request, 'Login.html')

def quanli(request):
    return render(request, 'quanli.html')

def vechungtoi(request):
    return render(request, 'vechungtoi.html')

def danhmuc_list(request):
    return render(request, 'danhmuc-list.html')

def danhmuc_form(request):
    return render(request, 'danhmuc-form.html')

def thucdon_list(request):
    return render(request, 'thucdon-list.html')

def thucdon_form(request):
    return render(request, 'thucdon-form.html')

def khachhang_list(request):
    return render(request, 'khachhang-list.html')

def khachhang_form(request):
    return render(request, 'khachhang-form.html')

def nhanvien_list(request):
    return render(request, 'nhanvien-list.html')

def nhanvien_form(request):
    return render(request, 'nhanvien-form.html')

def donhang_list(request):
    return render(request, 'donhang-list.html')

def donhang_form(request):
    return render(request, 'donhang-form.html')

def chitiet_list(request):
    return render(request, 'chitiet-list.html')

def chitiet_form(request):
    return render(request, 'chitiet-form.html')

def chitiet_pay(request):
    return render(request, 'chitiet-pay.html')

def chitiet_pay_success(request):
    return render(request, 'chitiet-pay-success.html')

def chitiet_pay_error(request):
    return render(request, 'chitiet-pay-error.html')

def khuyenmai_list(request):
    return render(request, 'khuyenmai-list.html')

def khuyenmai_form(request):
    return render(request, 'khuyenmai-form.html')

def timkiem_result(request):
    return render(request, 'timkiem-result.html')

def doanhthu(request):
    return render(request, 'Danhthu.html')

def error_page(request):
    return render(request, 'error-page.html')

def chi_nhanh(request):
    return render(request, 'chi_nhanh_gis.html')

def chuyencafe(request):
    return render(request, 'chuyencafe.html')

def Giaodienkh(request):
    return render(request, 'Giaodienkh.html')

def oder(request):
    return render(request, 'oder.html')