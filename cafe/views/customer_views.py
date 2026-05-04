from functools import wraps
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from cafe.views.staff_views import tru_nguyen_lieu
from ..models import Mon, DanhMuc
from ..models import QuanCafe
import math
from django.db import connection
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, transaction

# Chặn tài khoản nhân viên
# views.py (Đoạn đầu file)
def is_customer(user):
    # Trả về True nếu: Đã đăng nhập VÀ KHÔNG phải nhân viên VÀ KHÔNG phải admin tổng
    return user.is_authenticated and not user.is_staff and not user.is_superuser

def is_admin(user):
    # Trả về True nếu: Đã đăng nhập VÀ là Admin tổng (Superuser)
    return user.is_authenticated and user.is_superuser

# Trang chủ
def marketing_home(request):
    # Lấy 3 món ngẫu nhiên hoặc 3 món mới nhất để hiện ở trang chủ
    products = Mon.objects.all().order_by('?')[:3] 
    return render(request, "khachhang/base_main.html", {"products": products})
# --- HÀM HỖ TRỢ ---
def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách giữa 2 điểm GPS (km)"""
    try:
        R = 6371
        # Chuyển đổi sang radian và đảm bảo là số thực
        phi1, lam1 = math.radians(float(lat1)), math.radians(float(lon1))
        phi2, lam2 = math.radians(float(lat2)), math.radians(float(lon2))

        dphi = phi2 - phi1
        dlam = lam2 - lam1

        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return round(R * c, 2) # Làm tròn 2 chữ số thập phân
    except (TypeError, ValueError):
        return None

# --- VIEWS ---
def clean_coordinate(coord_str):
    if coord_str:
        # Thay thế dấu phẩy thành dấu chấm để ép kiểu float không bị lỗi
        return coord_str.replace(',', '.')
    return coord_str

import json
def shop(request):
    # --- GIỮ NGUYÊN PHẦN LẤY TỌA ĐỘ CỦA NÍ ---
    user_lat = clean_coordinate(request.GET.get("lat"))
    user_lon = clean_coordinate(request.GET.get("lon"))

    cafes = []
    nearest_cafe = None
    min_distance = float('inf')

    # --- TRUY VẤN SQL CÓ THÊM ẢNH & SAO ---
    with connection.cursor() as cursor:
        cursor.execute("""
        SELECT 
            q.macafe, q.tencafe, q.diachi, q.sodienthoai,
            ST_Y(q.geom::geometry) as lat,
            ST_X(q.geom::geometry) as lon,

            -- Ảnh đại diện
            (SELECT HINHANH 
             FROM ANH_QUANCAFE a 
             WHERE a.MACAFE = q.macafe 
             LIMIT 1) as anh_daidien,

            -- ⭐ FIX Ở ĐÂY
            COALESCE(
                (SELECT ROUND(AVG(SAO)::numeric, 1)::float 
                FROM DANHGIA r 
                WHERE r.MACAFE = q.macafe),
                0
            ) as sao_tb
        FROM quancafe q
        WHERE q.trang_thai = 'MO'
            """)
        rows = cursor.fetchall()

    # --- GIỮ NGUYÊN LOGIC TÍNH KHOẢNG CÁCH ---
    for row in rows:
        cafe_lat, cafe_lon = row[4], row[5]
        distance = None

        if user_lat and user_lon:
            distance = haversine(user_lat, user_lon, cafe_lat, cafe_lon)
            if distance is not None and distance < min_distance:
                min_distance = distance
                nearest_cafe = row[1]

        cafes.append({
            "id": row[0],
            "tencafe": row[1],
            "diachi": row[2],
            "sodienthoai": row[3],
            "lat": cafe_lat,
            "lon": cafe_lon,
            "distance": distance,
            "anh": row[6] if row[6] else 'default_cafe.jpg', # Thêm ảnh
            "sao": row[7] if row[7] else 0                    # Thêm sao
        })

    # --- GIỮ NGUYÊN LOGIC SẮP XẾP ---
    if user_lat and user_lon:
        cafes.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))

    context = {
        "cafes": cafes,
        "cafes_json": json.dumps(cafes), # Để truyền sang Javascript vẽ Map
        "nearest": nearest_cafe,
        "user_lat": user_lat,
        "user_lon": user_lon
    }
    
    return render(request, "khachhang/shop.html", context)
# đánh giá khách hàng 
# 2. Hàm lấy dữ liệu Ảnh & Review cho Modal
# 2. Hàm lấy dữ liệu Ảnh & Review cho Modal (Đã sửa lại cho khớp Model DANHGIA)
def get_store_data(request, ma_cafe):
    with connection.cursor() as cursor:
        # 1. Lấy ảnh không gian quán (Giữ nguyên)
        cursor.execute("SELECT HINHANH FROM ANH_QUANCAFE WHERE MACAFE = %s", [ma_cafe])
        images = [row[0] for row in cursor.fetchall()]

        # 2. Lấy review (Thêm cột PHANHOI_ADMIN vào đây)
        # Ní check lại tên cột trong DB của mình là gì nha, tui ví dụ là PHANHOI_ADMIN
        cursor.execute("""
            SELECT TENKHACH, NOIDUNG, SAO, HINHANH_REVIEW, PHAN_HOI_ADMIN 
            FROM DANHGIA 
            WHERE MACAFE = %s  
            ORDER BY NGAY_DG DESC
        """, [ma_cafe])
                
        raw_reviews = cursor.fetchall()
        reviews = []
        
        for r in raw_reviews:
            # Xử lý chuỗi ảnh review khách gửi
            anh_str = r[3] if r[3] else ""
            list_anh = [a.strip() for a in anh_str.split(',')] if anh_str else []
            
            reviews.append({
                "ten": r[0],
                "noidung": r[1],
                "sao": r[2],
                "images": list_anh,
               "phan_hoi_admin": r[4] # THÊM DÒNG NÀY: Gửi nội dung phản hồi về JS
            })

    return JsonResponse({"images": images, "reviews": reviews})

# 3. Hàm nhận Review từ khách (Đã sửa lại cho khớp Model DANHGIA)
@login_required(login_url='login')
@login_required(login_url='login')
@csrf_exempt
def gui_review(request):
    if request.method == "POST":
        try:
            ma_cafe = request.POST.get('ma_cafe')
            noidung = request.POST.get('noi_dung')
            sao = request.POST.get('so_sao')

            danh_sach_anh = request.FILES.getlist('anh_review')

            is_anon = request.POST.get('is_anonymous') == 'on'
            ten_hien_thi = "Người dùng ẩn danh" if is_anon else request.user.username 

            # Lưu nhiều ảnh
            danh_sach_path = []
            if danh_sach_anh:
                from django.core.files.storage import FileSystemStorage
                fs = FileSystemStorage()
                for anh in danh_sach_anh:
                    filename = fs.save(f"reviews/{anh.name}", anh)
                    danh_sach_path.append(filename)

            chuoi_anh_de_luu = ",".join(danh_sach_path) if danh_sach_path else None

            # ⭐ CHẶN 1 USER REVIEW 1 LẦN
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM DANHGIA 
                    WHERE USER_ID = %s AND MACAFE = %s
                """, [request.user.id, ma_cafe])

                if cursor.fetchone():
                    return JsonResponse({
                        "status": "error",
                        "message": "Bạn đã đánh giá quán này rồi!"
                    })

                # ⭐ INSERT ĐÚNG
                cursor.execute("""
                    INSERT INTO DANHGIA 
                    (MACAFE, USER_ID, TENKHACH, NOIDUNG, SAO, HINHANH_REVIEW, NGAY_DG)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [
                    ma_cafe,
                    request.user.id,
                    ten_hien_thi,
                    noidung,
                    sao,
                    chuoi_anh_de_luu,
                    timezone.now()
                ])

            return JsonResponse({"status": "success"})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)
# Trang giao hàng (KHÔNG bắt đăng nhập)
@user_passes_test(is_customer, login_url='/staff-dashboard/') # CHẶN Ở ĐÂY LUÔN
def order_home(request):

    categories = DanhMuc.objects.all()

    madanhmuc = request.GET.get("madanhmuc")

    if madanhmuc:
        products = Mon.objects.filter(madanhmuc=madanhmuc)
    else:
        products = Mon.objects.all()

    context = {
        "categories": categories,
        "products": products
    }

    return render(request, "khachhang/order_home.html", context)
# Trang tin tức
def news_home(request):
    return render(request, "khachhang/news.html")
# Trang thực đơn giới thiệu
@user_passes_test(is_customer, login_url='/staff-dashboard/') # CHẶN Ở ĐÂY LUÔN
def Menu(request):

    categories = DanhMuc.objects.all()

    madanhmuc = request.GET.get("madanhmuc")

    if madanhmuc:
        products = Mon.objects.filter(madanhmuc=madanhmuc)
    else:
        products = Mon.objects.all()

    context = {
        "categories": categories,
        "products": products
    }

    return render(request, "khachhang/Menu.html", context)
# Đăng ký
def register(request):

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        if User.objects.filter(username=username).exists():
            return render(request, "khachhang/register.html", {
                "error": "Tên đăng nhập đã tồn tại"
            })

        User.objects.create_user(username=username, password=password)

        return redirect('login')

    return render(request, "khachhang/register.html")
# Đăng nhập (Chỉ dùng 1 hàm duy nhất này thôi)
# Đăng nhập (Đã sửa lỗi phân luồng)
def user_login(request):
    if request.method == "POST":
        u = request.POST.get('username')
        p = request.POST.get('password')

        print(f"--- THỬ ĐĂNG NHẬP: User='{u}', Pass='{p}' ---")

        user = authenticate(username=u, password=p)

        if user is not None:
            login(request, user)
            print(f"--- THÀNH CÔNG: {u} đã vào hệ thống ---")
            
           # views.py -> hàm user_login
            if user.is_superuser:
                return redirect('admin_dashboard') 
            elif user.is_staff:
                return redirect('staff_dashboard') 
            else:
                # cuối cùng là khách hàng
                return redirect('/')
            
        else:
            print(f"--- THẤT BẠI: Sai pass hoặc User '{u}' không tồn tại ---")
            return render(request, "khachhang/login.html", {
                "error": "Tên đăng nhập hoặc mật khẩu không chính xác!"
            })

    return render(request, "khachhang/login.html")

def user_logout(request):
    logout(request)
    return redirect('login')
#giỏ hàng 
def add_to_cart(request):
    if request.method == "POST":
        # 1. Lấy ID món từ AJAX gửi lên
        mamon = request.POST.get('product_id')
        
        try:
            # Kiểm tra món có tồn tại trong bảng MON không
            mon_obj = Mon.objects.get(mamon=mamon)
            
            # 2. Lấy giỏ hàng hiện tại từ session (nếu chưa có thì tạo dict mới)
            # Cấu trúc: { 'id_mon': { 'ten': '...', 'gia': '...', 'soluong': 1 } }
            cart = request.session.get('cart', {})

            if mamon in cart:
                cart[mamon]['soluong'] += 1
            else:
                cart[mamon] = {
                    'tenmon': mon_obj.tenmon,
                    'giatien': float(mon_obj.giatien),
                    'soluong': 1,
                    'hinhanh': mon_obj.hinhanh if mon_obj.hinhanh else ""
                }

            # 3. Lưu lại vào session
            request.session['cart'] = cart
            
            # Tính tổng số lượng để hiện lên icon giỏ hàng (nếu cần)
            total_items = sum(item['soluong'] for item in cart.values())

            return JsonResponse({
                'status': 'success',
                'product_name': mon_obj.tenmon,
                'total_items': total_items
            })
            
        except Mon.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Món không tồn tại'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Yêu cầu không hợp lệ'}, status=400)
# xử lý giỏ hàng 
@login_required(login_url='login')
@user_passes_test(is_customer, login_url='/staff-dashboard/') # Nếu là staff, đá về dashboard
def view_cart(request):
    cart = request.session.get('cart', {})
    total_price = 0
    
    # Duyệt qua giỏ hàng để tính thành tiền cho từng món
    for key, value in cart.items():
        thanh_tien = float(value['giatien']) * int(value['soluong'])
        value['total_item_price'] = thanh_tien  # Tạo thêm 1 biến lưu thành tiền
        total_price += thanh_tien
    
    # Lưu lại vào session để cập nhật dữ liệu mới có total_item_price
    request.session['cart'] = cart
    
    context = {
        'cart': cart,
        'total_price': total_price,
    }
    return render(request, 'khachhang/cart.html', context)
# xóa khỏi giỏ hàng 
def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    
    # Nếu món có trong giỏ thì xóa sạch nó đi
    if str(product_id) in cart:
        del cart[str(product_id)]
        request.session['cart'] = cart
        request.session.modified = True
        
    return redirect('view_cart') # Sau khi xóa thì quay lại trang giỏ hàng
# thanh toán  
# 1. Hàm hiển thị trang Checkout
@user_passes_test(is_customer, login_url='/staff-dashboard/')
def checkout_view(request):
    cart = request.session.get('cart', {})
    
    # Lấy danh sách quán cafe CÓ KÈM TỌA ĐỘ
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT macafe, tencafe, diachi, 
                   ST_Y(geom::geometry) as lat, 
                   ST_X(geom::geometry) as lon 
            FROM quancafe
            WHERE trang_thai = 'MO'
        """)
        cafes = cursor.fetchall() # Bây giờ cafes[3] là lat, cafes[4] là lon

    # Tính tổng tiền giỏ hàng
    total_price = sum(float(v.get('giatien', 0)) * int(v.get('soluong', 0)) for v in cart.values())

    context = {
        'cart': cart,
        'cafes': cafes,
        'total_price': total_price,
    }
    return render(request, 'khachhang/checkout.html', context)


# 2. Xử lý khi bấm nút "Xác nhận đặt hàng"
# Sửa lại hàm place_order để tích hợp tính phí ship và lưu bảng GIAOHANG
# --- TÌM ĐẾN HÀM PLACE_ORDER VÀ SỬA ĐOẠN CUỐI ---
@user_passes_test(is_customer, login_url='/staff-dashboard/')
def place_order(request):
    if request.method == "POST":
        cart = request.session.get('cart', {})
        if not cart:
            return redirect('order_home')

        pttt_chon = request.POST.get('pttt') 
        ten_khach_nhap = request.POST.get('hoten')
        sdt_nhan = request.POST.get('sodienthoai')
        diachi_nhan = request.POST.get('diachi_giaohang')
        macafe = request.POST.get('macafe')
        
        try:
            u_lat = float(request.POST.get('user_lat', 0))
            u_lon = float(request.POST.get('user_lon', 0))
        except (ValueError, TypeError):
            u_lat, u_lon = 0, 0

        try:
            with transaction.atomic():  
             with connection.cursor() as cursor:
                # --- BƯỚC MỚI: KIỂM TRA QUÁN CÓ ĐANG MỞ KHÔNG ---
                cursor.execute("SELECT TRANG_THAI, TENCAFE FROM QUANCAFE WHERE MACAFE = %s", [macafe])
                quan_check = cursor.fetchone()
                
                if not quan_check or quan_check[0] != 'MO':
                    # Nếu quán đã đóng hoặc không tồn tại, báo lỗi và dừng xử lý
                    messages.error(request, f"Chi nhánh {quan_check[1] if quan_check else ''} hiện đã đóng cửa. Vui lòng chọn chi nhánh khác!")
                    return redirect('checkout_view')

                # 1. Xử lý khách hàng (Giữ nguyên của ní)
                cursor.execute("SELECT MAKH FROM KHACHHANG WHERE USER_ID = %s", [request.user.id])
                row = cursor.fetchone()
                geom_text = f'POINT({u_lon} {u_lat})'
                
                if row:
                    makh = row[0]
                    cursor.execute("""
                        UPDATE KHACHHANG SET TENKH=%s, SODIENTHOAI=%s, DIACHI=%s, GEOM=ST_GeogFromText(%s)
                        WHERE MAKH=%s
                    """, [ten_khach_nhap, sdt_nhan, diachi_nhan, geom_text, makh])
                else:
                    cursor.execute("""
                        INSERT INTO KHACHHANG (USER_ID, TENKH, SODIENTHOAI, DIACHI, EMAIL, GEOM)
                        VALUES (%s, %s, %s, %s, %s, ST_GeogFromText(%s)) RETURNING MAKH
                    """, [request.user.id, ten_khach_nhap, sdt_nhan, diachi_nhan, request.user.email, geom_text])
                    makh = cursor.fetchone()[0]

                # 2. Tính phí ship (Lấy tọa độ từ Database)
                cursor.execute("SELECT ST_Y(GEOM::geometry), ST_X(GEOM::geometry) FROM QUANCAFE WHERE MACAFE = %s", [macafe])
                shop_coord = cursor.fetchone()
                
                phi_ship = 0
                km = 0
                if shop_coord and u_lat != 0:
                    km = calculate_distance(shop_coord[0], shop_coord[1], u_lat, u_lon)
                    if km < 2: phi_ship = 0
                    elif km < 5: phi_ship = 15000
                    else: phi_ship = 15000 + (max(0, km - 5)) * 5000
                
                # 3. Tổng tiền
                tong_tien_mon = sum(float(v.get('giatien', 0)) * int(v.get('soluong', 0)) for v in cart.values())
                tong_thanh_toan = tong_tien_mon + phi_ship

                # 4. Lưu đơn hàng
                cursor.execute("""
                    INSERT INTO DONHANG (MAKH, MACAFE, THOIGIANDAT, TRANGTHAI, TONGTIEN, phuong_thuc_tt)
                    VALUES (%s, %s, %s, 'DANGXULY', %s, %s) RETURNING MADON
                """, [makh, macafe, timezone.now(), tong_thanh_toan, pttt_chon])
                madon = cursor.fetchone()[0]

                # 5. Lưu chi tiết và thông tin giao hàng
                for mamon_id, item in cart.items():
                    cursor.execute("INSERT INTO CHITIETDON (MADON, MAMON, SOLUONG, THANHTIEN, GIA_LUC_DAT) VALUES (%s, %s, %s, %s, %s)",
                                 [madon, mamon_id, item['soluong'], item.get('total_item_price', item['giatien'] * item['soluong']), item['giatien']])
                    # ⭐ TRỪ NGUYÊN LIỆU Ở ĐÂY
                tru_nguyen_lieu(cursor, mamon_id, item['soluong'], macafe)

                cursor.execute("""
                    INSERT INTO GIAOHANG (MADON, KHOANGCACH_KM, PHIVANCHUYEN, THOIGIAN_DUKIEN, TRANGTHAI)
                    VALUES (%s, %s, %s, %s, 'DANGGIAO')
                """, [madon, km, phi_ship, int(km * 5 + 10)])

            # Xóa giỏ hàng sau khi đặt thành công
            request.session['cart'] = {}
            request.session.modified = True
            messages.success(request, "Đặt hàng thành công!")
            return redirect('track_order', madon=madon)
            
        except Exception as e:
            return HttpResponse(f"Lỗi khi lưu đơn hàng: {e}")

    return redirect('view_cart')
# nút tăng chỉnh 
def update_cart(request, product_id, action):
    # 1. Lấy giỏ hàng từ session
    cart = request.session.get('cart', {})
    p_id = str(product_id)

    if p_id in cart:
        if action == 'plus':
            cart[p_id]['soluong'] += 1
        
        elif action == 'minus':
            cart[p_id]['soluong'] -= 1
            # Nếu giảm xuống 0 thì tự xóa luôn
            if cart[p_id]['soluong'] <= 0:
                del cart[p_id]
        
        elif action == 'remove':
            # Xóa hẳn món đó ra khỏi giỏ
            del cart[p_id]

        # 2. Tính toán lại tổng tiền cho món đó (để hiển thị ở cột Thành tiền)
        if p_id in cart:
            cart[p_id]['total_item_price'] = cart[p_id]['soluong'] * float(cart[p_id]['giatien'])

    # 3. Lưu lại vào session
    request.session['cart'] = cart
    request.session.modified = True
    
    return redirect('view_cart') # Nhớ đổi tên này đúng với name của URL giỏ hàng bạn đặt
from math import radians, cos, sin, asin, sqrt

# Hàm tính khoảng cách Haversine (tính đường chim bay giữa 2 tọa độ)
import math

def calculate_distance(lat1, lon1, lat2, lon2):
    # lat1, lon1: Tọa độ quán
    # lat2, lon2: Tọa độ khách
    
    R = 6371  # Bán kính Trái Đất (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance # Trả về số km (ví dụ: 5.2)

# Hàm tính tiền ship trong views
def get_shipping_fee(request):
    # Giả sử tọa độ quán của bạn (Quận 12)
    SHOP_LAT, SHOP_LON = 10.82646, 106.62054
    
    # Lấy tọa độ khách gửi từ frontend
    user_lat = float(request.POST.get('user_lat', 0))
    user_lon = float(request.POST.get('user_lon', 0))
    
    if user_lat == 0: return 0 # Tránh lỗi khi chưa lấy được vị trí
    
    km = calculate_distance(SHOP_LAT, SHOP_LON, user_lat, user_lon)
    
    # Logic tính tiền theo km
    if km < 2:
        fee = 0
    elif km < 5:
        fee = 15000
    else:
        fee = 15000 + (km - 5) * 5000 # 15k cho 5km đầu, sau đó 5k/km
        
    return int(fee)

@login_required(login_url='login')
def track_order(request, madon):
    with connection.cursor() as cursor:
        # SELECT thêm q.DIACHI (địa chỉ quán) để biết ở quận mấy
        cursor.execute("""
            SELECT dh.MADON, dh.THOIGIANDAT, dh.TONGTIEN, dh.TRANGTHAI, 
                   gh.PHIVANCHUYEN, gh.THOIGIAN_DUKIEN, q.TENCAFE, kh.TENKH, kh.DIACHI,
                   dh.phuong_thuc_tt,
                   q.DIACHI -- Cột index 10: Địa chỉ quán cafe
            FROM DONHANG dh
            LEFT JOIN GIAOHANG gh ON dh.MADON = gh.MADON
            JOIN QUANCAFE q ON dh.MACAFE = q.MACAFE
            JOIN KHACHHANG kh ON dh.MAKH = kh.MAKH
            WHERE dh.MADON = %s AND kh.USER_ID = %s
        """, [madon, request.user.id])
        
        row = cursor.fetchone()
        if not row:
            return HttpResponse("Không tìm thấy đơn hàng hoặc bạn không có quyền xem.")

        order = {
            'madon': row[0], 
            'thoigiandat': row[1], 
            'tongtien': row[2], 
            'trangthai': row[3], 
            'phi_ship': row[4], 
            'du_kien': row[5], 
            'tencafe': row[6], 
            'hoten': row[7], 
            'diachi_giaohang': row[8],
            'pttt': row[9],
            'diachi_quan': row[10] # Địa chỉ quán để hiện khu vực
        }

        # Lấy chi tiết món
        cursor.execute("""
            SELECT m.TENMON, ct.SOLUONG, ct.THANHTIEN 
            FROM CHITIETDON ct 
            JOIN MON m ON ct.MAMON = m.MAMON 
            WHERE ct.MADON = %s
        """, [madon])
        
        details = [dict(zip(['tenmon', 'soluong', 'thanhtien'], r)) for r in cursor.fetchall()]

    return render(request, 'khachhang/track_order.html', {'order': order, 'details': details})

@login_required(login_url='login')
def order_history(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT dh.MADON, dh.THOIGIANDAT, dh.TONGTIEN, dh.TRANGTHAI
            FROM DONHANG dh
            JOIN KHACHHANG kh ON dh.MAKH = kh.MAKH
            WHERE kh.USER_ID = %s
            ORDER BY dh.THOIGIANDAT DESC
        """, [request.user.id])
        
        columns = ['madon', 'thoigiandat', 'tongtien', 'trangthai']
        orders = [dict(zip(columns, r)) for r in cursor.fetchall()]

    return render(request, 'khachhang/order_history.html', {'orders': orders})
## Chặn quyền 
# views.py
