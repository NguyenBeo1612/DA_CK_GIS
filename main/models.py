from django.db import models

# =========================
# 1. DanhMuc
# =========================
class DanhMuc(models.Model):
    MaDanhMuc = models.AutoField(primary_key=True)
    TenDanhMuc = models.CharField(max_length=100)

    def __str__(self):
        return self.TenDanhMuc


# =========================
# 2. ThucDon
# =========================
class ThucDon(models.Model):
    MaMon = models.AutoField(primary_key=True)
    TenMon = models.CharField(max_length=100)
    MoTa = models.TextField(null=True, blank=True)
    Gia = models.DecimalField(max_digits=10, decimal_places=2)
    HinhAnh = models.CharField(max_length=255, null=True, blank=True)
    TinhTrang = models.BooleanField(default=True)
    SanPhamNoiBat = models.BooleanField(default=False)
    CoSize = models.BooleanField(default=False)

    MaDanhMuc = models.ForeignKey(
        DanhMuc,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.TenMon


# =========================
# 3. KhachHang
# =========================
class KhachHang(models.Model):
    MaKH = models.AutoField(primary_key=True)
    HoTen = models.CharField(max_length=100)
    Email = models.CharField(max_length=100)
    MatKhau = models.CharField(max_length=100)
    SoDienThoai = models.CharField(max_length=15)
    DiaChi = models.CharField(max_length=255)

    def __str__(self):
        return self.HoTen


# =========================
# 4. NhanVien
# =========================
class NhanVien(models.Model):
    MaNV = models.AutoField(primary_key=True)
    HoTen = models.CharField(max_length=100)
    ChucVu = models.CharField(max_length=50)
    Email = models.CharField(max_length=100)
    MatKhau = models.CharField(max_length=100)
    TinhTrang = models.BooleanField(default=True)

    def __str__(self):
        return self.HoTen


# =========================
# 5. DonHang
# =========================
class DonHang(models.Model):
    MaDon = models.AutoField(primary_key=True)
    NgayDat = models.DateField(auto_now_add=True)
    TongTien = models.DecimalField(max_digits=10, decimal_places=2)
    TrangThai = models.CharField(max_length=50)

    MaKH = models.ForeignKey(KhachHang, on_delete=models.CASCADE)
    MaNV = models.ForeignKey(NhanVien, on_delete=models.CASCADE)

    def __str__(self):
        return f"Đơn {self.MaDon}"


# =========================
# 6. Size
# =========================
class Size(models.Model):
    MaSize = models.AutoField(primary_key=True)
    TenSize = models.CharField(max_length=20)
    GiaTang = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.TenSize


# =========================
# 7. ChiTietDonHang
# =========================
class ChiTietDonHang(models.Model):
    MaChiTiet = models.AutoField(primary_key=True)

    MaDon = models.ForeignKey(DonHang, on_delete=models.CASCADE)
    MaMon = models.ForeignKey(ThucDon, on_delete=models.CASCADE)
    MaSize = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True)

    SoLuong = models.IntegerField(default=1)
    DonGia = models.DecimalField(max_digits=10, decimal_places=2)
    PhuThu = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ThanhTien = models.DecimalField(max_digits=10, decimal_places=2, default=0)


# =========================
# 8. DoanhThu
# =========================
class DoanhThu(models.Model):
    Ngay = models.DateField(primary_key=True)
    TongDon = models.IntegerField()
    TongSoLuong = models.IntegerField()
    TongDoanhThu = models.DecimalField(max_digits=10, decimal_places=2)
