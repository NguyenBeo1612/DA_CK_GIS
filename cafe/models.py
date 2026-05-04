from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import connection

# --- DANH MỤC & MÓN ---
class DanhMuc(models.Model):
    madanhmuc = models.AutoField(primary_key=True)
    tendanhmuc = models.CharField(max_length=200)
    class Meta:
        db_table = "danhmuc"
        managed = False

class Mon(models.Model):
    mamon = models.AutoField(primary_key=True)
    tenmon = models.CharField(max_length=200)
    giatien = models.DecimalField(max_digits=10, decimal_places=2)
    mota = models.TextField(null=True, blank=True)
    hinhanh = models.TextField(null=True, blank=True)
    madanhmuc = models.ForeignKey(DanhMuc, on_delete=models.CASCADE, db_column='madanhmuc')
    class Meta:
        db_table = "mon"
        managed = False
    def __str__(self):
        return self.tenmon

# --- HỆ THỐNG CHI NHÁNH & NHÂN VIÊN ---
class QuanCafe(models.Model):
    macafe = models.AutoField(primary_key=True)
    tencafe = models.CharField(max_length=200)
    diachi = models.TextField(null=True, blank=True)
    sodienthoai = models.CharField(max_length=15, null=True, blank=True)
    geom = models.TextField() # PostGIS field
    class Meta:
        db_table = "quancafe"
        managed = False

class NhanVien(models.Model):
    manv = models.AutoField(primary_key=True) # Khớp với MANV SERIAL trong SQL
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_column='user_id')
    tennv = models.CharField(max_length=200)
    sodienthoai = models.CharField(max_length=15, null=True, blank=True)
    email = models.CharField(max_length=200, null=True, blank=True)
    macafe = models.ForeignKey(QuanCafe, on_delete=models.CASCADE, db_column='macafe')
    class Meta:
        db_table = "nhanvien"
        managed = False

# --- KHÁCH HÀNG ---
class KhachHang(models.Model):
    makh = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, db_column='user_id')
    tenkh = models.CharField(max_length=200)
    sodienthoai = models.CharField(max_length=15, null=True, blank=True)
    email = models.CharField(max_length=200, null=True, blank=True)
    diachi = models.TextField(null=True, blank=True)
    geom = models.TextField() # PostGIS field
    class Meta:
        db_table = "khachhang"
        managed = False

# --- ĐƠN HÀNG & CHI TIẾT ---
class DonHang(models.Model):
    madon = models.AutoField(primary_key=True)
    makh = models.ForeignKey(KhachHang, on_delete=models.SET_NULL, null=True, db_column='makh')
    macafe = models.ForeignKey(QuanCafe, on_delete=models.CASCADE, db_column='macafe')
    manv = models.ForeignKey(NhanVien, on_delete=models.SET_NULL, null=True, db_column='manv') # Cột mới
    thoigiandat = models.DateTimeField(auto_now_add=True)
    trangthai = models.CharField(max_length=50, default='DANGXULY')
    tongtien = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Cột mới
    loaidon = models.CharField(max_length=20, default='ONLINE') # Cột mới
    class Meta:
        db_table = "donhang"
        managed = False

class ChiTietDon(models.Model):
    mact = models.AutoField(primary_key=True)
    madon = models.ForeignKey(DonHang, on_delete=models.CASCADE, db_column='madon')
    mamon = models.ForeignKey(Mon, on_delete=models.CASCADE, db_column='mamon')
    soluong = models.IntegerField()
    thanhtien = models.DecimalField(max_digits=10, decimal_places=2)
    gia_luc_dat = models.DecimalField(max_digits=10, decimal_places=2) # Cột mới
    class Meta:
        db_table = "chitietdon"
        managed = False
class StaffProfile(models.Model):
    # Kết nối 1-1 với tài khoản User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Danh sách các chi nhánh
    BRANCH_CHOICES = [
        ('Q3', 'Quận 3'),
        ('Q7', 'Quận 7'),
    ]
    chi_nhanh = models.CharField(max_length=10, choices=BRANCH_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.get_chi_nhanh_display()}"
## Đánh giá của khách 
# --- ĐÁNH GIÁ (REVIEW) ---
class DanhGia(models.Model):
    ma_dg = models.AutoField(primary_key=True, db_column='ma_dg')

    macafe = models.ForeignKey(
        QuanCafe,
        on_delete=models.CASCADE,
        db_column='macafe',
        related_name='reviews'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='user_id'
    )

    tenkhach = models.CharField(max_length=200)
    noidung = models.TextField(null=True, blank=True)
    sao = models.IntegerField()
    hinhanh_review = models.TextField(null=True, blank=True)

    ngay_dg = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "danhgia"
        managed = False
        unique_together = ('user', 'macafe')  # backup thêm ở Django