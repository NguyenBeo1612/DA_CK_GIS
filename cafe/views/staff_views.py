import json
import os
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.utils import timezone  # cái này để lấy ngày hiện tại
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, connection 
from django.contrib import messages             # cái này dùng để messages để hiện thông báo lỗi/thành công
from django.contrib.auth.models import User     # người dùng để tạo tài khoản
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from cafe.decorators import admin_required
from cafe_project import settings 

# 1. Hàm kiểm tra quyền nhân viên
def is_staff(user):
    return user.is_authenticated and user.is_staff

@login_required(login_url='login')
def staff_dashboard(request):
    with connection.cursor() as cursor:
        # 1. Lấy thông tin nhân viên và quán
        cursor.execute("""
            SELECT nv.TENNV, qc.TENCAFE, nv.MACAFE, nv.MANV
            FROM NHANVIEN nv
            JOIN QUANCAFE qc ON nv.MACAFE = qc.MACAFE
            WHERE nv.USER_ID = %s
        """, [request.user.id])
        row = cursor.fetchone()

        if row:
            ten_nv, ten_quan, ma_cafe, ma_nv = row
            today_str = timezone.now().strftime('%Y-%m-%d')

            # 2. Lấy các số liệu thống kê (Gộp vào 1 lần query để tối ưu)
            # Đếm đơn mới
            cursor.execute("SELECT COUNT(*) FROM DONHANG WHERE MACAFE = %s AND TRANGTHAI = 'DANGXULY' AND DATE(THOIGIANDAT) = %s", [ma_cafe, today_str])
            don_moi = cursor.fetchone()[0]

            # Đếm đơn xong
            cursor.execute("SELECT COUNT(*) FROM DONHANG WHERE MACAFE = %s AND TRANGTHAI = 'HOANTHANH' AND DATE(THOIGIANDAT) = %s", [ma_cafe, today_str])
            don_xong = cursor.fetchone()[0]

            # Tổng đơn trong ngày
            cursor.execute("SELECT COUNT(*) FROM DONHANG WHERE MACAFE = %s AND DATE(THOIGIANDAT) = %s", [ma_cafe, today_str])
            tong_don = cursor.fetchone()[0]

            # Doanh thu
            cursor.execute("SELECT COALESCE(SUM(TONGTIEN), 0) FROM DONHANG WHERE MACAFE = %s AND TRANGTHAI = 'HOANTHANH' AND DATE(THOIGIANDAT) = %s", [ma_cafe, today_str])
            doanh_thu_raw = cursor.fetchone()[0]
            doanh_thu = "{:,.0f}".format(float(doanh_thu_raw)).replace(',', '.')

            context = {
                'ten_nv': ten_nv,
                'ten_quan': ten_quan,
                'don_moi': don_moi,
                'don_xong': don_xong,
                'tong_don': tong_don,
                'doanh_thu': doanh_thu,
            }
        else:
            context = {
                'ten_nv': "Nhân viên",
                'ten_quan': "Hệ thống CafeHouse",
                'don_moi': 0, 'don_xong': 0, 'tong_don': 0, 'doanh_thu': "0",
            }
            
    return render(request, 'NhanVien/base_staff.html', context)
# 3. Trang danh sách đơn hàng (Giữ nguyên nhưng thêm cột TENKH cho Pro)
@user_passes_test(is_staff, login_url='login')
def staff_order_list(request):
    status_filter = request.GET.get('status', 'DANGXULY')
    
    # SỬA Ở ĐÂY: Truyền username (email) vào hàm helper
    ma_cafe = get_staff_macafe(request.user.id)
    
    if not ma_cafe:
        return render(request, 'NhanVien/order_list.html', {
            'orders': [], 
            'error': 'Tài khoản chưa được gán vào chi nhánh nào trong hệ thống!'
        })

    orders = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT dh.*, COALESCE(dh.tenkh, kh.TENKH, 'Khách Online') AS tenkh_display
            FROM DONHANG dh
            LEFT JOIN KHACHHANG kh ON dh.MAKH = kh.MAKH
            WHERE dh.MACAFE = %s AND dh.TRANGTHAI = %s AND dh.LOAIDON != 'TAIQUAY'
            ORDER BY dh.THOIGIANDAT DESC
        """, [ma_cafe, status_filter])
        
        columns = [col[0] for col in cursor.description]
        orders = [dict(zip(columns, r)) for r in cursor.fetchall()]

    return render(request, 'NhanVien/order_list.html', {
        'orders': orders, 
        'current_status': status_filter
    })
@user_passes_test(is_staff, login_url='login')
def complete_order(request, order_id):
    if request.method == "POST":
        # SỬA Ở ĐÂY: Truyền username (email) thay vì user.id
       # SỬA: Thay username bằng id
        ma_cafe_staff = get_staff_macafe(request.user.id)
        
        try:
            with connection.cursor() as cursor:
                # Kiểm tra xem đơn hàng này có thuộc về quán của nhân viên này không
                cursor.execute("SELECT MACAFE FROM DONHANG WHERE MADON = %s", [order_id])
                order_row = cursor.fetchone()
                
                # Nếu không tìm thấy quán của nhân viên hoặc quán không khớp với đơn hàng
                if not ma_cafe_staff or not order_row or order_row[0] != ma_cafe_staff:
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'Không có quyền xử lý đơn này hoặc tài khoản chưa gán quán!'
                    }, status=403)

                # Cập nhật trạng thái đơn hàng
                cursor.execute("UPDATE DONHANG SET TRANGTHAI = 'HOANTHANH' WHERE MADON = %s", [order_id])
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return JsonResponse({'status': 'error', 'message': 'Yêu cầu không hợp lệ!'}, status=400)
# Lên đơn tại quầy 
# Lên đơn tại quầy 
@login_required(login_url='login')
def pos_view(request):
    # 1. LẤY THÔNG TIN NHÂN VIÊN (Dùng user_id để khớp 100% với tài khoản đang login)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT nv.manv, nv.tennv, qc.macafe, qc.tencafe 
            FROM nhanvien nv
            JOIN quancafe qc ON nv.macafe = qc.macafe
            WHERE nv.user_id = %s
        """, [request.user.id])
        staff_info = cursor.fetchone()

    # Kiểm tra nếu tài khoản staff này chưa có hồ sơ trong bảng NHANVIEN
    if not staff_info:
        return HttpResponse(f"""
            <div style="text-align:center; margin-top:50px; font-family:sans-serif;">
                <h2 style="color:red;">Lỗi Phân Quyền Chi Nhánh</h2>
                <p>Tài khoản <b>{request.user.username}</b> (ID: {request.user.id}) chưa được gán vào chi nhánh nào.</p>
                <p>Vui lòng liên hệ Admin để cập nhật bảng NHANVIEN.</p>
                <a href="/staff-dashboard/">Quay lại Dashboard</a>
            </div>
        """)

    staff_id, staff_name, branch_id, branch_name = staff_info

    # 2. XỬ LÝ LƯU ĐƠN HÀNG (Khi nhấn Thanh toán từ giao diện POS)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cart = data.get('cart', [])
            total_amount = data.get('total', 0)
            customer = data.get('customer', 'Khách vãng lai')
            payment_method = data.get('payment_method', 'Tiền mặt')

            if not cart:
                return JsonResponse({'status': 'error', 'message': 'Giỏ hàng trống!'})
            
            with transaction.atomic():
               with connection.cursor() as cursor:
                # Lưu thông tin khách và PTTT vào ghi chú hoặc tên khách
                info_khach = f"{customer} ({payment_method})"

                # Tạo đơn hàng mới (Trạng thái HOANTHANH vì bán tại quầy)
                cursor.execute("""
                    INSERT INTO DONHANG (MACAFE, MANV, THOIGIANDAT, TRANGTHAI, TONGTIEN, LOAIDON, TENKH)
                    VALUES (%s, %s, %s, 'HOANTHANH', %s, 'TAIQUAY', %s) RETURNING MADON
                """, [branch_id, staff_id, timezone.now(), total_amount, info_khach])
                
                order_id = cursor.fetchone()[0]

                # Lưu chi tiết từng món trong đơn hàng
                for item in cart:
                    cursor.execute("""
                        INSERT INTO CHITIETDON (MADON, MAMON, SOLUONG, THANHTIEN, GIA_LUC_DAT)
                        VALUES (%s, %s, %s, %s, %s)
                    """, [order_id, item['id'], item['quantity'], float(item['price']) * int(item['quantity']), item['price']])
                    # trừ kho nguyên liệu 
                    tru_nguyen_lieu(cursor, item['id'], item['quantity'], branch_id)
            
            return JsonResponse({
                'status': 'success', 
                'order_id': order_id,
                'message': f'Thanh toán thành công tại {branch_name}'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    # 3. LẤY DANH SÁCH MÓN ĂN ĐỂ HIỂN THỊ MENU
    with connection.cursor() as cursor:
        cursor.execute("SELECT mamon, tenmon, giatien, hinhanh FROM mon ORDER BY tenmon ASC")
        products = cursor.fetchall()

    # 4. TRUYỀN DỮ LIỆU RA GIAO DIỆN
    context = {
        'staff_name': staff_name,    # Hiện tên: Leo Q3
        'branch_name': branch_name,  # Hiện tên quán: CafeHouse Quận 3
        'products': products,        # Danh sách món
    }
    return render(request, "NhanVien/pos_terminal.html", context)

# Tìm đến chỗ này và sửa lại
# Tìm đến hàm này ở gần cuối file và sửa lại:
def get_staff_macafe(user_id): 
    with connection.cursor() as cursor:
        # Tìm chi nhánh dựa trên USER_ID (ID của tài khoản đang login)
        cursor.execute("SELECT MACAFE FROM NHANVIEN WHERE USER_ID = %s", [user_id])
        row = cursor.fetchone()
        return row[0] if row else None
# Xử lý admin 
# 1. Hàm kiểm tra quyền Admin
def is_admin(user):
    return user.is_authenticated and user.is_superuser

@admin_required
def admin_dashboard(request):
    with connection.cursor() as cursor:
        # 1. THỐNG KÊ TỔNG QUÁT (3 ô Card phía trên)
        # Sử dụng đúng các trạng thái đơn hàng như bên revenue_report
        cursor.execute("""
            SELECT 
                -- Ô 1: Đơn Online đang chờ (NOT IN các trạng thái đã xong/hủy)
                COUNT(CASE WHEN TRANGTHAI NOT IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DAHUY', 'DA_THANH_TOAN') THEN 1 END) as don_moi,
                -- Ô 2: Tổng đơn hoàn thành (Khớp số 29)
                COUNT(CASE WHEN TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN') THEN 1 END) as tong_don_xong,
                -- Ô 3: Tổng doanh thu hệ thống (Khớp số 1.730.429 - tính cả ship)
                COALESCE(SUM(CASE WHEN TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN') THEN TONGTIEN END), 0) +
                COALESCE((SELECT SUM(PHIVANCHUYEN) FROM GIAOHANG gh 
                          JOIN DONHANG d2 ON gh.MADON = d2.MADON 
                          WHERE d2.TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')), 0) as doanh_thu_tong
            FROM DONHANG
        """)
        tong_moi, tong_don_xong, doanh_thu_tong_raw = cursor.fetchone()

        # 2. THỐNG KÊ CHI TIẾT TỪNG QUÁN (Bảng Hiệu suất)
        # Dùng Subquery để tính toán chuẩn xác theo từng chi nhánh
        cursor.execute("""
            SELECT 
                qc.TENCAFE, 
                qc.DIACHI, 
                (SELECT COUNT(*) FROM DONHANG d1 
                 WHERE d1.MACAFE = qc.MACAFE 
                 AND d1.TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')) as so_don,
                
                COALESCE((SELECT SUM(d2.TONGTIEN) FROM DONHANG d2 
                          WHERE d2.MACAFE = qc.MACAFE 
                          AND d2.TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')), 0) +
                COALESCE((SELECT SUM(gh.PHIVANCHUYEN) FROM GIAOHANG gh 
                          JOIN DONHANG d3 ON gh.MADON = d3.MADON 
                          WHERE d3.MACAFE = qc.MACAFE 
                          AND d3.TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')), 0) as doanh_thu
            FROM QUANCAFE qc
            ORDER BY doanh_thu DESC
        """)
        
        raw_data = cursor.fetchall()
        thong_ke_quan = []
        for r in raw_data:
            thong_ke_quan.append({
                'TENCAFE': r[0],
                'DIACHI': r[1],
                'so_don': r[2],
                'doanh_thu_fmt': "{:,.0f}".format(float(r[3])).replace(',', '.')
            })

        # 3. Lấy tên Admin từ bảng NHANVIEN
        cursor.execute("SELECT TENNV FROM NHANVIEN WHERE USER_ID = %s", [request.user.id])
        admin_row = cursor.fetchone()
        ten_hien_thi = admin_row[0] if admin_row else request.user.username

    context = {
        'ten_admin': ten_hien_thi,
        'don_moi': tong_moi,                                     
        'tong_don': tong_don_xong,                               
        'doanh_thu': "{:,.0f}".format(float(doanh_thu_tong_raw)).replace(',', '.'), 
        'thong_ke_quan': thong_ke_quan,                         
    }
    return render(request, 'Admin/dashboard_admin.html', context)
# 1. Danh sách chi nhánh (Admin nhìn thấy hết)
# Sửa lại đoạn này trong staff_views.py

@admin_required
def quan_ly_chi_nhanh(request):
    search_query = request.GET.get('search', '').strip()
    with connection.cursor() as cursor:
        # --- 1. Thống kê (Giữ nguyên của ní) ---
        cursor.execute("SELECT 1, 1, 0") # Demo fetch
        tong_moi, tong_don_xong, doanh_thu_tong = cursor.fetchone()

        # --- 2. Lấy danh sách quán ---
        query = """
            SELECT MACAFE, TENCAFE, DIACHI, SODIENTHOAI, GIOMO, GIODONG, trang_thai,
                   ST_X(GEOM::geometry) as lon, ST_Y(GEOM::geometry) as lat
            FROM QUANCAFE
            WHERE TENCAFE ILIKE %s OR DIACHI ILIKE %s
            ORDER BY MACAFE ASC
        """
        search_param = f'%{search_query}%'
        cursor.execute(query, [search_param, search_param])
        columns = [col[0].lower() for col in cursor.description]
        ds_quancafe = [dict(zip(columns, r)) for r in cursor.fetchall()]

        # --- 3. Gộp lấy Ảnh và Đánh giá cho từng quán ---
        for cafe in ds_quancafe:
            # Lấy ảnh không gian quán
            cursor.execute("SELECT HINHANH FROM ANH_QUANCAFE WHERE MACAFE = %s", [cafe['macafe']])
            cafe['images'] = [r[0] for r in cursor.fetchall()]
            
            # Lấy đánh giá của chi nhánh này
            cursor.execute("""
                    SELECT 
                        MA_DG, 
                        TENKHACH, 
                        NOIDUNG, 
                        SAO, 
                        HINHANH_REVIEW, 
                        PHAN_HOI_ADMIN, 
                        NGAY_PHAN_HOI, 
                        NGAY_DG 
                    FROM DANHGIA 
                    WHERE MACAFE = %s 
                    ORDER BY NGAY_DG DESC
                """, [cafe['macafe']])
            
            rev_cols = [col[0].lower() for col in cursor.description]
            reviews = [dict(zip(rev_cols, row)) for row in cursor.fetchall()]

            # --- LOGIC MỚI: Xử lý tách chuỗi ảnh đánh giá ---
            for rev in reviews:
                if rev['hinhanh_review']:
                    # Tách chuỗi bằng dấu phẩy và xóa khoảng trắng thừa
                    # Kết quả là một list: ['reviews/anh1.jpg', 'reviews/anh2.jpg']
                    rev['list_anh_review'] = [img.strip() for img in rev['hinhanh_review'].split(',') if img.strip()]
                else:
                    rev['list_anh_review'] = []
            
            cafe['reviews'] = reviews

    context = {
        'ds_quancafe': ds_quancafe,
        'don_moi': tong_moi,
        'tong_don': tong_don_xong,
        'doanh_thu': "{:,.0f}".format(doanh_thu_tong).replace(',', '.'),
        'search_query': search_query,
    }
    return render(request, 'Admin/quan_ly_chi_nhanh.html', context)
# 2. Thêm chi nhánh mới (Có xử lý tọa độ GIS)
@user_passes_test(is_admin, login_url='login')
def them_chi_nhanh(request):
    if request.method == "POST":
        ten = request.POST.get('tencafe')
        dc = request.POST.get('diachi')
        sdt = request.POST.get('sdt')
        mo = request.POST.get('giomo')
        dong = request.POST.get('giodong')
        lat = request.POST.get('lat')
        lng = request.POST.get('lng')

        with connection.cursor() as cursor:
            # 1. Lưu quán và lấy ID
            cursor.execute("""
                INSERT INTO QUANCAFE (TENCAFE, DIACHI, SODIENTHOAI, GIOMO, GIODONG, GEOM, trang_thai)
                VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'MO')
                RETURNING MACAFE
            """, [ten, dc, sdt, mo, dong, lng, lat])
            
            macafe_moi = cursor.fetchone()[0]

            # 2. Xử lý lưu ảnh vào Static/chinhanh
            files = request.FILES.getlist('hinhanh_quan')
            if files:
                # Lấy đường dẫn thư mục Static (nhảy ra khỏi thư mục hinhanh)
                # MEDIA_ROOT của ní là .../Static/hinhanh -> dirname sẽ lấy .../Static/
                static_path = os.path.dirname(settings.MEDIA_ROOT)
                upload_path = os.path.join(static_path, 'chinhanh')
                
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                fs = FileSystemStorage(location=upload_path)
                
                for f in files:
                    filename = fs.save(f.name, f)
                    # Lưu vào DB đường dẫn tương đối để dễ gọi: "chinhanh/ten_anh.jpg"
                    file_db_path = f"chinhanh/{filename}"
                    
                    cursor.execute("""
                        INSERT INTO ANH_QUANCAFE (MACAFE, HINHANH, MO_TA)
                        VALUES (%s, %s, %s)
                    """, [macafe_moi, file_db_path, f"Không gian {ten}"])

        return redirect('quan_ly_chi_nhanh')
    return render(request, 'Admin/them_chi_nhanh.html')
# 3. Sửa trạng thái (Đóng/Mở nhanh)
@user_passes_test(is_admin, login_url='login')
def doi_trang_thai_quan(request, ma_cafe, trang_thai_moi):
    # Chuẩn hóa giá trị để khớp với Database (ví dụ ép về in hoa)
    trang_thai_moi = str(trang_thai_moi).upper() 
    
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE QUANCAFE 
            SET trang_thai = %s 
            WHERE MACAFE = %s
        """, [trang_thai_moi, ma_cafe])
        
    return redirect('quan_ly_chi_nhanh')
# 4. Hàm Cập nhật thông tin chi nhánh (Dành cho nút Sửa)
# Trong staff_views.py
@user_passes_test(is_admin, login_url='login')
def cap_nhat_chi_nhanh(request, ma_cafe):
    if request.method == "POST":
        # 1. Lấy thông tin từ Form
        ten = request.POST.get('tencafe')
        diachi = request.POST.get('diachi')
        sdt = request.POST.get('sdt')
        giomo = request.POST.get('giomo')
        giodong = request.POST.get('giodong')
        lat = request.POST.get('lat')
        lng = request.POST.get('lng')

        with connection.cursor() as cursor:
            # 2. Cập nhật bảng chính QUANCAFE (Dùng ST_MakePoint cho cột GEOM)
            # PostGIS: lng trước, lat sau
            cursor.execute("""
                UPDATE QUANCAFE 
                SET TENCAFE = %s, 
                    DIACHI = %s, 
                    SODIENTHOAI = %s, 
                    GIOMO = %s, 
                    GIODONG = %s,
                    GEOM = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                WHERE MACAFE = %s
            """, [ten, diachi, sdt, giomo, giodong, lng, lat, ma_cafe])

            # 3. Xử lý ảnh mới (nếu khách chọn thêm ảnh lúc sửa)
            files = request.FILES.getlist('hinhanh_quan')
            if files:
                # Đường dẫn tuyệt đối đến thư mục Static/chinhanh
                # Ní lưu ý: Đảm bảo thư mục này nằm trong cafe/Static/chinhanh nhé
                upload_path = os.path.join('cafe', 'Static', 'chinhanh')
                
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                fs = FileSystemStorage(location=upload_path)
                
                for f in files:
                    # Lưu file vật lý
                    filename = fs.save(f.name, f)
                    # Đường dẫn lưu vào DB để hiển thị (thường bắt đầu từ chinhanh/...)
                    file_db_path = f"chinhanh/{filename}"
                    
                    # Thêm ảnh mới vào bảng ANH_QUANCAFE
                    cursor.execute("""
                        INSERT INTO ANH_QUANCAFE (MACAFE, HINHANH, MO_TA) 
                        VALUES (%s, %s, %s)
                    """, [ma_cafe, file_db_path, 'Ảnh cập nhật'])

        return redirect('quan_ly_chi_nhanh')

    # Nếu là GET thì redirect về trang quản lý hoặc xử lý render tùy logic của ní
    return redirect('quan_ly_chi_nhanh')
# Xóa chi nhánh 
# Sửa 'macafe' thành 'ma_cafe' cho khớp với urls.py
def xoa_chi_nhanh(request, ma_cafe): 
    from django.db import connection
    import os

    with connection.cursor() as cursor:
        # 1. Lấy danh sách đường dẫn ảnh để xóa file vật lý
        cursor.execute("SELECT HINHANH FROM ANH_QUANCAFE WHERE MACAFE = %s", [ma_cafe])
        anh_list = cursor.fetchall()

        # 2. Xóa quán (Nếu có ON DELETE CASCADE thì ảnh trong DB tự mất)
        cursor.execute("DELETE FROM QUANCAFE WHERE MACAFE = %s", [ma_cafe])

        # 3. Quét và xóa file thực tế trong thư mục Static
        for row in anh_list:
            if row[0]:
                full_path = os.path.join('cafe', 'Static', row[0])
                if os.path.exists(full_path):
                    os.remove(full_path)

    return redirect('quan_ly_chi_nhanh')
# phản hồi đánh giá 
# =========================================
# QUẢN LÝ ĐÁNH GIÁ & PHẢN HỒI (ADMIN)
# =========================================
# Hàm này xử lý khi Admin nhấn nút "Gửi" trên giao diện
@user_passes_test(is_admin, login_url='login')
def luu_phan_hoi_admin(request, ma_dg):
    if request.method == "POST":
        noi_dung_rep = request.POST.get('noi_dung_rep')
        
        if noi_dung_rep: # Kiểm tra tránh trường hợp gửi nội dung rỗng
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE DANHGIA 
                    SET PHAN_HOI_ADMIN = %s, NGAY_PHAN_HOI = CURRENT_TIMESTAMP
                    WHERE MA_DG = %s
                """, [noi_dung_rep, ma_dg])
            messages.success(request, "Đã phản hồi khách hàng thành công!")
        else:
            messages.error(request, "Nội dung phản hồi không được để trống.")
    
    # Dùng HTTP_REFERER để quay lại đúng trang danh sách đánh giá bạn đang xem
    # Nếu không lấy được trang trước đó thì mới về 'quan_ly_chi_nhanh'
    return redirect(request.META.get('HTTP_REFERER', 'quan_ly_chi_nhanh'))
## Trang quản lí nhân viên 
def quan_ly_nhan_vien(request):
    with connection.cursor() as cursor:
        query = """
            SELECT 
                nv.MANV, 
                nv.TENNV, 
                nv.CHUCVU, 
                nv.SODIENTHOAI, 
                nv.EMAIL, 
                nv.MACAFE,
                qc.TENCAFE AS TEN_QUAN
            FROM NHANVIEN nv
            LEFT JOIN QUANCAFE qc ON nv.MACAFE = qc.MACAFE
            ORDER BY (CASE WHEN nv.CHUCVU = 'Chủ tịch' THEN 0 ELSE 1 END), nv.MANV DESC
        """
        # QUAN TRỌNG: Phải có dòng này trước khi lấy description
        cursor.execute(query) 
        
        # Kiểm tra xem cursor có description không để tránh lỗi 500
        if cursor.description:
            columns = [col[0].upper() for col in cursor.description]
            ds_nhan_vien = [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            ds_nhan_vien = []

        # Lấy thêm danh sách quán để hiện trong Modal (cái này ní cũng cần)
        cursor.execute("SELECT MACAFE, TENCAFE FROM QUANCAFE")
        columns_qc = [col[0].upper() for col in cursor.description]
        ds_quancafe = [dict(zip(columns_qc, row)) for row in cursor.fetchall()]

    return render(request, 'Admin/quan_ly_nhan_vien.html', {
        'ds_nhan_vien': ds_nhan_vien,
        'ds_quancafe': ds_quancafe
    })
@user_passes_test(is_admin, login_url='login')
def them_nhan_vien(request):
    if request.method == 'POST':
        tennv = request.POST.get('tennv')
        chucvu = request.POST.get('chucvu')
        sdt = request.POST.get('sdt')
        email = request.POST.get('email')
        macafe = request.POST.get('macafe')
        password = request.POST.get('password')

        try:
            with transaction.atomic(): 
                # 1. Tạo tài khoản đăng nhập Django (auth_user)
                if User.objects.filter(username=email).exists():
                    messages.error(request, f"Email {email} đã được sử dụng!")
                    return redirect('quan_ly_nhan_vien')
                
                # Tạo User mới
                user = User.objects.create_user(username=email, email=email, password=password)
                user.first_name = tennv
                user.is_staff = True  # Để họ có quyền vào dashboard nhân viên
                user.save()

                # 2. Lưu vào bảng NHANVIEN (Bổ sung cột USER_ID)
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO NHANVIEN (TENNV, CHUCVU, SODIENTHOAI, EMAIL, MACAFE, USER_ID)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [tennv, chucvu, sdt, email, macafe if macafe else None, user.id])

            messages.success(request, f"Đã thêm nhân viên {tennv} và tạo tài khoản thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi hệ thống: {e}")

    return redirect('quan_ly_nhan_vien')

@user_passes_test(is_admin, login_url='login')
def cap_nhat_nhan_vien(request, ma_nv):
    if request.method == "POST":
        ten = request.POST.get('tennv')
        chucvu = request.POST.get('chucvu')
        sdt = request.POST.get('sdt')
        email_moi = request.POST.get('email')
        macafe = request.POST.get('macafe')

        try:
            with transaction.atomic():
                # 1. Lấy email cũ để tìm tài khoản Django tương ứng
                with connection.cursor() as cursor:
                    cursor.execute("SELECT EMAIL FROM NHANVIEN WHERE MANV = %s", [ma_nv])
                    row = cursor.fetchone()
                    if not row:
                        messages.error(request, "Không tìm thấy nhân viên!")
                        return redirect('quan_ly_nhan_vien')
                    email_cu = row[0]

                    # 2. Cập nhật bảng NHANVIEN
                    cursor.execute("""
                        UPDATE NHANVIEN
                        SET TENNV = %s, CHUCVU = %s, SODIENTHOAI = %s, EMAIL = %s, MACAFE = %s
                        WHERE MANV = %s
                    """, [ten, chucvu, sdt, email_moi, macafe if macafe else None, ma_nv])

                # 3. Đồng bộ cập nhật Email/Username bên bảng User của Django
                # Vì ní dùng Email làm Username để đăng nhập nên phải đổi cả hai
                User.objects.filter(username=email_cu).update(
                    username=email_moi, 
                    email=email_moi,
                    first_name=ten
                )

                messages.success(request, f"Đã cập nhật thông tin nhân viên {ten}!")
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật: {e}")
            
        return redirect('quan_ly_nhan_vien')
    
    return redirect('quan_ly_nhan_vien')
@user_passes_test(is_admin, login_url='login')
def xoa_nhan_vien(request, ma_nv):
    with connection.cursor() as cursor:
        cursor.execute("SELECT EMAIL FROM NHANVIEN WHERE MANV = %s", [ma_nv])
        row = cursor.fetchone()
        if row:
            email = row[0]
            # Xóa ở bảng nhân viên 
            cursor.execute("DELETE FROM NHANVIEN WHERE MANV = %s", [ma_nv])
            User.objects.filter(username=email).delete()
    messages.success(request, " Đã xóa nhân viên và vô hiệu hóa tài khoản")
    # Xóa xong thì quay về trang danh sách
    return redirect('quan_ly_nhan_vien')
# 1. Trang danh sách danh mục
# 1. Trang danh sách danh mục
@user_passes_test(is_admin, login_url='login')
def category_list(request):
    with connection.cursor() as cursor:
        # Sửa tên bảng thành DANHMUC
        cursor.execute("SELECT MADANHMUC, TENDANHMUC FROM DANHMUC ORDER BY MADANHMUC DESC")
        categories = cursor.fetchall()
    
    return render(request, 'Admin/category_list.html', {'categories': categories})

# 2. Thêm danh mục mới
@user_passes_test(is_admin, login_url='login')
def add_category(request):
    if request.method == "POST":
        ten_danhmuc = request.POST.get('ten_loai') # 'ten_loai' là name từ input HTML
        if ten_danhmuc:
            with connection.cursor() as cursor:
                # Sửa tên bảng và cột
                cursor.execute("INSERT INTO DANHMUC (TENDANHMUC) VALUES (%s)", [ten_danhmuc])
        return redirect('category_list')
    return render(request, 'Admin/add_category.html')

# 3. Xóa danh mục
@user_passes_test(is_admin, login_url='login')
def delete_category(request, madanhmuc):
    with connection.cursor() as cursor:
        try:
            # Sửa tên bảng và cột
            cursor.execute("DELETE FROM DANHMUC WHERE MADANHMUC = %s", [madanhmuc])
        except Exception as e:
            print(f"Lỗi khi xóa: {e}")
    return redirect('category_list')
@user_passes_test(is_admin, login_url='login')
def edit_category(request, madanhmuc):
    if request.method == "POST":
        ten_moi = request.POST.get('ten_loai')
        if ten_moi:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE DANHMUC 
                    SET TENDANHMUC = %s 
                    WHERE MADANHMUC = %s
                """, [ten_moi, madanhmuc])
        return redirect('category_list')
    return redirect('category_list')
# 1. DANH SÁCH THỰC ĐƠN
@user_passes_test(is_admin, login_url='login')
def menu_list(request):
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()

    with connection.cursor() as cursor:
        # THÊM m.MOTA vào cuối câu SELECT
        query = """
            SELECT m.MAMON, m.TENMON, m.GIATIEN, d.TENDANHMUC, m.HINHANH, m.MADANHMUC, m.MOTA
            FROM MON m
            LEFT JOIN DANHMUC d ON m.MADANHMUC = d.MADANHMUC
            WHERE 1=1
        """
        params = []
        if search_query:
            query += " AND m.TENMON ILIKE %s"
            params.append(f'%{search_query}%')
        if category_filter:
            query += " AND m.MADANHMUC = %s"
            params.append(category_filter)

        query += " ORDER BY m.MAMON DESC"
        cursor.execute(query, params)
        menu_items = cursor.fetchall()
        
        cursor.execute("SELECT MADANHMUC, TENDANHMUC FROM DANHMUC ORDER BY TENDANHMUC ASC")
        categories = cursor.fetchall()
        
    return render(request, 'Admin/menu_list.html', {
        'menu_items': menu_items,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter
    })

# 2. THÊM MÓN MỚI
@user_passes_test(is_admin, login_url='login')
def add_menu_item(request):
    if request.method == "POST":
        ten_mon = request.POST.get('ten_mon')
        gia = request.POST.get('gia')
        ma_dm = request.POST.get('madanhmuc')
        mo_ta = request.POST.get('mo_ta') # Lấy mô tả mới
        
        file_anh = request.FILES.get('hinh_anh')
        ten_file_de_luu = ""
        if file_anh:
            fs = FileSystemStorage()
            filename = fs.save(file_anh.name, file_anh)
            ten_file_de_luu = filename 

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO MON (TENMON, GIATIEN, MADANHMUC, HINHANH, MOTA)
                VALUES (%s, %s, %s, %s, %s)
            """, [ten_mon, gia, ma_dm, ten_file_de_luu, mo_ta])
        
        messages.success(request, f"Đã thêm món '{ten_mon}' thành công!")
    return redirect('menu_list')

# 3. CẬP NHẬT MÓN ĂN
@user_passes_test(is_admin, login_url='login')
def edit_menu_item(request, ma_mon):
    if request.method == "POST":
        ten_mon = request.POST.get('ten_mon')
        gia = request.POST.get('gia')
        ma_dm = request.POST.get('madanhmuc')
        mo_ta = request.POST.get('mo_ta') # Lấy mô tả cập nhật
        file_anh = request.FILES.get('hinh_anh') 
        
        with connection.cursor() as cursor:
            if file_anh:
                fs = FileSystemStorage()
                filename = fs.save(file_anh.name, file_anh)
                cursor.execute("""
                    UPDATE MON SET TENMON=%s, GIATIEN=%s, MADANHMUC=%s, HINHANH=%s, MOTA=%s
                    WHERE MAMON=%s
                """, [ten_mon, gia, ma_dm, filename, mo_ta, ma_mon])
            else:
                cursor.execute("""
                    UPDATE MON SET TENMON=%s, GIATIEN=%s, MADANHMUC=%s, MOTA=%s
                    WHERE MAMON=%s
                """, [ten_mon, gia, ma_dm, mo_ta, ma_mon])
        
        messages.success(request, f"Đã cập nhật món #{ma_mon}")
    return redirect('menu_list')
# 3. CẬP NHẬT MÓN ĂN
# 3. CẬP NHẬT MÓN ĂN
@user_passes_test(is_admin, login_url='login')
def edit_menu_item(request, ma_mon):
    if request.method == "POST":
        ten_mon = request.POST.get('ten_mon')
        gia = request.POST.get('gia')
        ma_dm = request.POST.get('madanhmuc')
        # QUAN TRỌNG: Phải có dòng này để lấy dữ liệu từ ô "Mô tả"
        mo_ta = request.POST.get('mo_ta') 
        
        file_anh = request.FILES.get('hinh_anh') 
        
        with connection.cursor() as cursor:
            if file_anh:
                fs = FileSystemStorage()
                filename = fs.save(file_anh.name, file_anh)
                # Thêm MOTA=%s vào câu UPDATE
                cursor.execute("""
                    UPDATE MON SET TENMON=%s, GIATIEN=%s, MADANHMUC=%s, HINHANH=%s, MOTA=%s
                    WHERE MAMON=%s
                """, [ten_mon, gia, ma_dm, filename, mo_ta, ma_mon])
            else:
                # Trường hợp không đổi ảnh cũng phải cập nhật MOTA
                cursor.execute("""
                    UPDATE MON SET TENMON=%s, GIATIEN=%s, MADANHMUC=%s, MOTA=%s
                    WHERE MAMON=%s
                """, [ten_mon, gia, ma_dm, mo_ta, ma_mon])
        
        messages.success(request, f"Đã cập nhật món #{ma_mon}")
    return redirect('menu_list')

# 4. XÓA MÓN ĂN
# 4. XÓA MÓN ĂN (Đã sửa để xóa cả dữ liệu liên quan)
@user_passes_test(is_admin, login_url='login')
def delete_menu_item(request, ma_mon):
    try:
        with connection.cursor() as cursor:
            # Bước 1: Xóa món này khỏi tất cả các chi tiết đơn hàng trước
            # Nếu không xóa ở đây, PostgreSQL sẽ báo lỗi IntegrityError như ní vừa thấy
            cursor.execute("DELETE FROM CHITIETDON WHERE MAMON = %s", [ma_mon])
            
            # Bước 2: Bây giờ mới an tâm xóa món ăn trong bảng MON
            cursor.execute("DELETE FROM MON WHERE MAMON = %s", [ma_mon])
        
        messages.warning(request, f"Đã xóa món ăn (Mã: {ma_mon}) và các dữ liệu liên quan thành công.")
    except Exception as e:
        # Nếu có lỗi gì khác (ví dụ lỗi kết nối DB), nó sẽ báo ở đây
        messages.error(request, f"Lỗi khi xóa: {str(e)}")
        
    return redirect('menu_list')
#Doanh thu
def revenue_report(request):
    # Lấy từ khóa tìm kiếm từ thanh Search
    search_query = request.GET.get('search', '').strip()

    with connection.cursor() as cursor:
        # 1. Tổng doanh thu hệ thống (Chỉ tính đơn đã hoàn thành)
        cursor.execute("""
            SELECT COALESCE(SUM(TONGTIEN), 0)
            FROM DONHANG
            WHERE TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')
        """)
        tong_cong_raw = cursor.fetchone()[0] or 0
        tong_doanh_thu = "{:,.0f}".format(float(tong_cong_raw)).replace(',', '.')

        # 2. Tổng đơn hoàn thành
        cursor.execute("""
            SELECT COUNT(*) FROM DONHANG 
            WHERE TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')
        """)
        tong_don_xong = cursor.fetchone()[0]

        # 3. Đơn đang chờ (Các đơn chưa xong và chưa hủy)
        cursor.execute("""
            SELECT COUNT(*) FROM DONHANG 
            WHERE TRANGTHAI NOT IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DAHUY', 'DA_THANH_TOAN')
        """)
        don_cho = cursor.fetchone()[0]

        # 4. Chi tiết chi nhánh: Tiền món, Tiền Ship, Tổng cộng & Đếm loại đơn
        query = """
            SELECT 
                q.TENCAFE, 
                q.DIACHI,
                COALESCE(SUM(d.TONGTIEN), 0) AS tong_cong,
                COALESCE(SUM(gh.PHIVANCHUYEN), 0) AS tien_ship,
                (COALESCE(SUM(d.TONGTIEN), 0) - COALESCE(SUM(gh.PHIVANCHUYEN), 0)) AS tien_mon,
                COUNT(CASE WHEN d.LOAIDON ILIKE '%%ONLINE%%' THEN 1 END) as don_on,
                COUNT(CASE WHEN d.LOAIDON ILIKE '%%TAIQUAY%%' OR d.LOAIDON ILIKE '%%Tại quầy%%' THEN 1 END) as don_tq
            FROM QUANCAFE q
            LEFT JOIN DONHANG d ON q.MACAFE = d.MACAFE 
                 AND d.TRANGTHAI IN ('HOANTHANH', 'COMPLETED', 'HOANTANH', 'DA_THANH_TOAN')
            LEFT JOIN GIAOHANG gh ON d.MADON = gh.MADON
            WHERE q.TENCAFE ILIKE %s OR q.DIACHI ILIKE %s
            GROUP BY q.MACAFE, q.TENCAFE, q.DIACHI
            ORDER BY tong_cong DESC
        """
        search_param = f'%{search_query}%'
        cursor.execute(query, [search_param, search_param])
        raw_branches = cursor.fetchall()
        
        doanh_thu_chi_nhanh = []
        for row in raw_branches:
            ten, diachi, tong, ship, mon, d_on, d_tq = row
            doanh_thu_chi_nhanh.append({
                'ten': ten,
                'diachi': diachi,
                'tien_mon': "{:,.0f}".format(float(mon)).replace(',', '.'),
                'tien_ship': "{:,.0f}".format(float(ship)).replace(',', '.'),
                'tong_cong': "{:,.0f}".format(float(tong)).replace(',', '.'),
                'don_on': d_on,
                'don_tai_quay': d_tq
            })

    # Lấy tên admin hiển thị
    ten_admin = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "CHỦ TỊCH"

    return render(request, 'Admin/revenue.html', {
        'tong_doanh_thu': tong_doanh_thu,
        'tong_don_xong': tong_don_xong,
        'don_cho': don_cho,
        'doanh_thu_chi_nhanh': doanh_thu_chi_nhanh,
        'search_query': search_query,
        'ten_admin': ten_admin,
    })
# =========================================
# QUẢN LÝ KHO & NGUYÊN LIỆU (STAFF)
@login_required(login_url='login')
def staff_inventory(request):
    with connection.cursor() as cursor:
        # 1. LẤY DANH SÁCH CHI NHÁNH (Giữ nguyên)
        cursor.execute("SELECT macafe, tencafe FROM quancafe ORDER BY macafe")
        cafe_list = [{"macafe": r[0], "tencafe": r[1]} for r in cursor.fetchall()]

        # 2. LẤY CHI NHÁNH ĐANG CHỌN & TRANG HIỆN TẠI
        cafe_id = request.GET.get('cafe_id')
        page_number = request.GET.get('page', 1) # Mặc định là trang 1
        
        ten_quan = "Tất cả chi nhánh"
        query_sql = """
            SELECT 
                manl, tennl, soluongton, donvitinh, macafe, muc_toi_thieu,
                CASE WHEN soluongton <= muc_toi_thieu THEN 1 ELSE 0 END AS bao_dong
            FROM nguyenlieu
        """
        params = []

        # 3. LOAD KHO THEO CHI NHÁNH
        if cafe_id and cafe_id != "":
            cursor.execute("SELECT tencafe FROM quancafe WHERE macafe = %s", [cafe_id])
            row = cursor.fetchone()
            if row:
                ten_quan = row[0]
            
            query_sql += " WHERE macafe = %s"
            params.append(cafe_id)
        
        query_sql += " ORDER BY bao_dong DESC, tennl ASC"
        
        # Thực thi lấy toàn bộ data để Paginator tính toán
        cursor.execute(query_sql, params)
        columns = [col[0].lower() for col in cursor.description]
        all_inventory = [dict(zip(columns, r)) for r in cursor.fetchall()]

        # 4. THỰC HIỆN PHÂN TRANG (PAGINATION)
        # Ní để khoảng 10-15 dòng mỗi trang cho đẹp nhé
        paginator = Paginator(all_inventory, 10) 
        page_obj = paginator.get_page(page_number)

        # 5. THỐNG KÊ (Dựa trên toàn bộ danh sách all_inventory)
        du_hang = len([i for i in all_inventory if i["bao_dong"] == 0])
        sap_het = len([i for i in all_inventory if i["bao_dong"] == 1])

    return render(request, 'Admin/inventory_staff.html', {
        'inventory': page_obj,  # Truyền page_obj thay vì list thuần
        'cafe_list': cafe_list,
        'ten_quan': ten_quan,
        'du_hang': du_hang,
        'sap_het': sap_het,
        'cafe_id': cafe_id
    })

@login_required(login_url='login')
def update_stock(request):
    cafe_id = request.POST.get('cafe_id')
    # Tạo sẵn URL để dùng chung cho tất cả các trường hợp redirect
    redirect_url = f"/inventory/?cafe_id={cafe_id}" if cafe_id else "/inventory/"

    if request.method == "POST":
        ma_nl = request.POST.get('ma_nl')
        so_luong_nhap = request.POST.get('so_luong_nhap')

        if not so_luong_nhap:
            messages.error(request, "Vui lòng nhập số lượng!")
            return redirect(redirect_url)

        try:
            val_nhap = float(so_luong_nhap)
            if val_nhap <= 0:
                messages.error(request, "Số lượng phải > 0!")
                return redirect(redirect_url)

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE nguyenlieu
                    SET soluongton = COALESCE(soluongton, 0) + %s
                    WHERE manl = %s
                """, [val_nhap, ma_nl])

            messages.success(request, "Nhập kho thành công!")

        except Exception as e:
            messages.error(request, f"Lỗi: {e}")

    return redirect(redirect_url)

def add_material(request):
    if request.method == "POST":
        ten_nl = request.POST.get('ten_nl')
        don_vi = request.POST.get('don_vi')
        muc_toi_thieu = request.POST.get('muc_toi_thieu')
        ton_kho = request.POST.get('ton_kho', 0)
        ma_cafe = request.POST.get('cafe_id')

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO nguyenlieu (tennl, donvitinh, muc_toi_thieu, soluongton, macafe)
                VALUES (%s, %s, %s, %s, %s)
            """, [ten_nl, don_vi, muc_toi_thieu, ton_kho, ma_cafe])
            
    return redirect('inventory_staff') # Hoặc name của route kho hàng
# trừ nguyên liệu
def tru_nguyen_lieu(cursor, ma_mon, so_luong, ma_cafe):
    # 1. Lấy công thức món
    cursor.execute("""
        SELECT manl, soluong_tieuhao
        FROM congthuc
        WHERE mamon = %s
    """, [ma_mon])

    congthuc = cursor.fetchall()

    if not congthuc:
        raise Exception("Món này chưa có công thức nguyên liệu!")

    # 2. Check trước toàn bộ nguyên liệu (tránh trừ dở dang)
    for manl, tieu_hao in congthuc:
        tong_tru = float(tieu_hao) * int(so_luong)

        cursor.execute("""
            SELECT COALESCE(soluongton, 0)
            FROM nguyenlieu
            WHERE manl = %s AND macafe = %s
        """, [manl, ma_cafe])

        row = cursor.fetchone()

        if not row:
            raise Exception("Không tìm thấy nguyên liệu trong kho!")

        ton = float(row[0])

        if ton < tong_tru:
            raise Exception("Không đủ nguyên liệu để thực hiện đơn hàng!")

    # 3. Nếu tất cả OK → mới bắt đầu trừ kho
    for manl, tieu_hao in congthuc:
        tong_tru = float(tieu_hao) * int(so_luong)

        cursor.execute("""
            UPDATE nguyenlieu
            SET soluongton = COALESCE(soluongton, 0) - %s
            WHERE manl = %s AND macafe = %s
        """, [tong_tru, manl, ma_cafe])
from django.http import HttpResponse
import csv

from django.http import HttpResponse
from django.db import connection
import csv
from openpyxl import Workbook
from django.http import HttpResponse
from django.db import connection
from openpyxl.styles import Font

def export_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Doanh thu"

    ws.append([
        'Chi nhánh',
        'Địa chỉ',
        'Đơn Online',
        'Đơn Tại quầy',
        'Tiền món',
        'Tiền ship',
        'Tổng doanh thu'
    ])

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                qc.tencafe,
                qc.diachi,
                COUNT(CASE WHEN UPPER(TRIM(dh.loaidon)) = 'ONLINE' THEN 1 END),
                COUNT(CASE WHEN UPPER(TRIM(dh.loaidon)) = 'TAIQUAY' THEN 1 END),
                COALESCE(SUM(dh.tongtien), 0),
                COALESCE(SUM(gh.phivanchuyen), 0),
                COALESCE(SUM(dh.tongtien), 0) + COALESCE(SUM(gh.phivanchuyen), 0)
            FROM quancafe qc
            LEFT JOIN donhang dh 
                ON dh.macafe = qc.macafe
                AND dh.trangthai = 'HOANTHANH'
            LEFT JOIN giaohang gh 
                ON gh.madon = dh.madon
            GROUP BY qc.macafe, qc.tencafe, qc.diachi
        """)

        for row in cursor.fetchall():
            ws.append(row)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="bao_cao_doanh_thu.xlsx"'

    wb.save(response)
    return response
import csv
from django.http import HttpResponse
from django.db import connection
from openpyxl.styles import Alignment, Font, PatternFill
def export_inventory(request):
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="kho_nguyen_lieu.xlsx"'

    wb = Workbook()
    ws = wb.active
    ws.title = "Kho nguyên liệu"

    # ===== HEADER =====
    headers = [
        'Tên nguyên liệu',
        'Đơn vị',
        'Tổng tồn kho',
        'Trạng thái',
        'Chi nhánh'
    ]

    ws.append(headers)

    # format header
    for col in ws[1]:
        col.font = Font(bold=True)
        col.alignment = Alignment(horizontal='center')

    cafe_id = request.GET.get('cafe_id')

    with connection.cursor() as cursor:
        query = """
            SELECT 
                nl.tennl,
                nl.donvitinh,
                SUM(nl.soluongton) AS tong_ton,
                CASE 
                    WHEN SUM(nl.soluongton) < MAX(nl.muc_toi_thieu) THEN 'Cần nhập'
                    ELSE 'Ổn định'
                END AS trang_thai,
                qc.tencafe
            FROM nguyenlieu nl
            JOIN quancafe qc ON nl.macafe = qc.macafe
        """

        params = []

        # fix lỗi cafe_id = None
        if cafe_id and cafe_id != "None":
            query += " WHERE nl.macafe = %s"
            params.append(int(cafe_id))

        query += """
            GROUP BY nl.tennl, nl.donvitinh, qc.tencafe
            ORDER BY qc.tencafe, nl.tennl
        """

        cursor.execute(query, params)

        # ===== DATA =====
        for row in cursor.fetchall():
            ws.append(row)

    # auto width cột
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max_length + 2

    wb.save(response)
    return response