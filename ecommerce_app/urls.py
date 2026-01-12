from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('user_register/', views.UserRegister, name="user_register"),
    path('user_login/', views.UserLogin, name="user_login"),
    path('user_logout/', views.UserLogout, name="user_logout"),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name="add_to_cart"),
    path('cart/', views.cart_view, name="cart"),
    path('update-cart-item/<int:item_id>/', views.update_cart_item, name="update_cart_item"),
    path('remove-cart-item/<int:item_id>/', views.remove_cart_item, name="remove_cart_item"),
    path('buy-now/<int:product_id>/', views.buy_now, name="buy_now"),
    path('checkout/', views.checkout, name="checkout"),
    path('place-order/', views.place_order, name="place_order"),
    path('order-details/<int:order_id>/', views.order_details, name="order_details"),
    path('download-invoice/<int:order_id>/', views.download_invoice, name="download_invoice"),
    path('your-orders/', views.your_orders, name="your_orders"),
]
