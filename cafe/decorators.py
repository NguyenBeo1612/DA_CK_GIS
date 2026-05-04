from functools import wraps
from django.shortcuts import redirect, render

def error_403_staff(request):
    return render(request, "Khachhang/403_staff.html")

def error_403_customer(request):
    return render(request, "khachhang/403_customer.html")


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if request.user.is_staff:
            return error_403_staff(request)

        return error_403_customer(request)

    return _wrapped_view