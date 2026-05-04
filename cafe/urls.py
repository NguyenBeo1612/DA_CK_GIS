from django.urls import path

from cafe_project import settings
# Sửa dòng này: phải trỏ vào thư mục con .views
from .views import customer_views 
from django.urls import path, include
from django.conf.urls.static import static

urlpatterns = [
    path("", customer_views.marketing_home, name="home"), 
    path('', include('cafe.urls_staff')),
    path("login/", customer_views.user_login, name="login"),
    path("order/", customer_views.order_home, name="order_home"),
    path("news/", customer_views.news_home, name="news"),
    path('register/', customer_views.register, name="register"),
    path('logout/', customer_views.user_logout, name="logout"),
    path("Menu/", customer_views.Menu, name="Menu"),
    # chi nhánh
    path("Shop/", customer_views.shop, name="shop"),
    path('get-store-data/<int:ma_cafe>/', customer_views.get_store_data, name='get_store_data'),
    path('gui-review/', customer_views.gui_review, name='gui_review'),

    path('add-to-cart/', customer_views.add_to_cart, name='add_to_cart'), 
    path('cart/', customer_views.view_cart, name='view_cart'),      
    path('remove/<int:product_id>/', customer_views.remove_from_cart, name='remove_from_cart'),
    path('create-order/', customer_views.view_cart, name='create_order'), 
    path('checkout/', customer_views.checkout_view, name='checkout'),
    path('place-order/', customer_views.place_order, name='place_order'),
    path('cart/update/<str:product_id>/<str:action>/', customer_views.update_cart, name='update_cart'),
    #giao diện nhân viên 
    path('staff/', include('cafe.urls_staff')),
    # Lịch sử đơn
    # Trong file urls.py
    path('track-order/<int:madon>/', customer_views.track_order, name='track_order'),
    path('order-history/', customer_views.order_history, name='order_history'),
    path('post-review/', customer_views.gui_review, name='gui_review'),
    ## hàm check quyền
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)