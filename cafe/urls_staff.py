# cafe/urls_staff.py
from django.urls import path
from .views import staff_views # Kiểm tra đường dẫn import này
from django.conf import settings # Thêm dòng này
from django.conf.urls.static import static # Thêm dòng này

urlpatterns = [
     # quản lý nguyên liệu
   path('inventory/', staff_views.staff_inventory, name='inventory_staff'),

    # Xử lý cập nhật kho
    path('inventory/update/', staff_views.update_stock, name='update_stock'),
    # URL xử lý việc thêm nguyên liệu mới hoàn toàn từ Modal
    path('inventory/add/', staff_views.add_material, name='add_material'),
    path('', staff_views.staff_dashboard, name='staff_dashboard'),
    # Dòng này là dòng gây lỗi nếu trong staff_views.py chưa có hàm staff_order_list
    path('orders/', staff_views.staff_order_list, name='staff_orders'),
    path('NhanVien/pos/', staff_views.pos_view, name='pos_terminal'),
    path('complete-order/<int:order_id>/', staff_views.complete_order, name='complete_order'),
    path('admin-tong/', staff_views.admin_dashboard, name='admin_dashboard'),
    path('quan-ly-chi-nhanh/', staff_views.quan_ly_chi_nhanh, name='quan_ly_chi_nhanh'),
    path('doi-trang-thai/<int:ma_cafe>/<str:trang_thai_moi>/', staff_views.doi_trang_thai_quan, name='doi_trang_thai_quan'),
    path('staff/cap-nhat-chi-nhanh/<int:ma_cafe>/', staff_views.cap_nhat_chi_nhanh, name='cap_nhat_chi_nhanh'),
    path('admin/chi-nhanh/xoa/<int:ma_cafe>/', staff_views.xoa_chi_nhanh, name='xoa_chi_nhanh'),
    path('luu-phan-hoi-admin/<int:review_id>/', staff_views.luu_phan_hoi_admin, name='luu_phan_hoi_admin'),
    path('admin/danh-gia/rep/<int:ma_dg>/', staff_views.luu_phan_hoi_admin, name='luu_phan_hoi_admin'),
    # Đảm bảo có thêm dòng này cho nút Thêm chi nhánh:
    path('them-chi-nhanh/', staff_views.them_chi_nhanh, name='them_chi_nhanh'),
    path('quan-ly-nhan-vien/', staff_views.quan_ly_nhan_vien, name='quan_ly_nhan_vien'),
    
    # Sẵn tiện thêm luôn 2 đường dẫn Thêm và Sửa để tí nữa nhấn nút không bị lỗi tiếp:
    path('quan-ly-nhan-vien/them/', staff_views.them_nhan_vien, name='them_nhan_vien'),
    path('quan-ly-nhan-vien/sua/<int:ma_nv>/', staff_views.cap_nhat_nhan_vien, name='cap_nhat_nhan_vien'),
    path('quan-ly-nhan-vien/xoa/<int:ma_nv>/', staff_views.xoa_nhan_vien, name='xoa_nhan_vien'),
    # Danh mục 
    path('admin/categories/', staff_views.category_list, name='category_list'),
    path('admin/categories/add/', staff_views.add_category, name='add_category'),
    # Fix maloai thành madanhmuc cho đúng logic SQL của ní
    path('admin/categories/delete/<int:madanhmuc>/', staff_views.delete_category, name='delete_category'),
    # Bổ sung path sửa danh mục
    path('admin/categories/edit/<int:madanhmuc>/', staff_views.edit_category, name='edit_category'),
    # QUẢN LÝ THỰC ĐƠN (MÓN ĂN)
    path('admin/menu/', staff_views.menu_list, name='menu_list'),
    path('admin/menu/add/', staff_views.add_menu_item, name='add_menu_item'),
    path('admin/menu/edit/<int:ma_mon>/', staff_views.edit_menu_item, name='edit_menu_item'),
    path('admin/menu/delete/<int:ma_mon>/', staff_views.delete_menu_item, name='delete_menu_item'),
    # Quản lý Doanh thu (Bước cuối cùng ní vừa yêu cầu)
    path('admin/revenue/', staff_views.revenue_report, name='revenue'),
    # Trong cafe/urls_staff.py của ní:
    path('admin/menu/add/', staff_views.add_menu_item, name='add_menu_item'),
    path('export-excel/', staff_views.export_excel, name='export_excel'),
    path('staff/export-inventory/', staff_views.export_inventory, name='export_inventory'),

   
]   
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)