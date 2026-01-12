from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from .forms import CustomerForm
from .models import Customer, Product, Cart, CartItem, Order, OrderItem
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Sum
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO


def get_or_create_cart(customer):
    cart, created = Cart.objects.get_or_create(customer=customer)
    return cart


def is_logged_in(request):
    return 'user_id' in request.session


def home(request):
    products = Product.objects.filter(is_active=True)
    cart_count = 0
    user = None
    
    if is_logged_in(request):
        user_id = request.session.get('user_id')
        user = Customer.objects.get(id=user_id)
        cart = get_or_create_cart(user)
        cart_count = cart.cartitem_set.aggregate(total=Sum('quantity'))['total'] or 0
    
    context = {
        'products': products,
        'cart_count': cart_count,
        'user': user,
    }
    return render(request, "index.html", context)


def UserRegister(request):
    form = CustomerForm()
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('user_login')
    return render(request, 'user_register.html', {'form': form})


def UserLogin(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = Customer.objects.filter(username=username, password=password).first()
        if user:
            request.session['user_id'] = user.id
            return redirect('home')
        else:
            return render(request, 'user_login.html', {'error': 'Invalid username or password'}) 
    else:
        return render(request, 'user_login.html')


def UserLogout(request):
    if 'user_id' in request.session:
        del request.session['user_id']
    request.session.flush()
    logout(request)
    return redirect("home")


def add_to_cart(request, product_id):
    if not is_logged_in(request):
        return redirect('user_login')
    
    product = get_object_or_404(Product, id=product_id, is_active=True)
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    cart = get_or_create_cart(user)
    
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart!')
    return redirect('home')


def cart_view(request):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    cart = get_or_create_cart(user)
    cart_items = cart.cartitem_set.all()
    
    if not cart_items.exists():
        return render(request, 'cart.html', {'empty': True, 'user': user})
    
    total = sum(item.get_total() for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'user': user,
    }
    return render(request, 'cart.html', context)


def update_cart_item(request, item_id):
    if not is_logged_in(request):
        return JsonResponse({'error': 'Not logged in'}, status=403)
    
    cart_item = get_object_or_404(CartItem, id=item_id)
    user_id = request.session.get('user_id')
    
    if cart_item.cart.customer.id != user_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
            else:
                cart_item.delete()
                return JsonResponse({'deleted': True})
        
        cart_item.save()
        return JsonResponse({
            'quantity': cart_item.quantity,
            'item_total': float(cart_item.get_total()),
            'cart_total': float(cart_item.cart.get_total())
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


def remove_cart_item(request, item_id):
    if not is_logged_in(request):
        return redirect('user_login')
    
    cart_item = get_object_or_404(CartItem, id=item_id)
    user_id = request.session.get('user_id')
    
    if cart_item.cart.customer.id != user_id:
        messages.error(request, 'Unauthorized action')
        return redirect('cart')
    
    cart_item.delete()
    messages.success(request, 'Item removed from cart')
    return redirect('cart')


def buy_now(request, product_id):
    if not is_logged_in(request):
        return redirect('user_login')
    
    product = get_object_or_404(Product, id=product_id, is_active=True)
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    
    context = {
        'product': product,
        'quantity': 1,
        'total': product.price,
        'user': user,
        'single_item': True,
    }
    return render(request, 'checkout.html', context)


def checkout(request):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    cart = get_or_create_cart(user)
    cart_items = cart.cartitem_set.all()
    
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty')
        return redirect('cart')
    
    total = sum(item.get_total() for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'user': user,
        'single_item': False,
    }
    return render(request, 'checkout.html', context)


def place_order(request):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    
    if request.method == 'POST':
        shipping_address = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method')
        single_product_id = request.POST.get('single_product_id')
        quantity = int(request.POST.get('quantity', 1))
        
        if single_product_id:
            # Single product order
            product = get_object_or_404(Product, id=single_product_id)
            total_amount = product.price * quantity
            
            order = Order.objects.create(
                customer=user,
                total_amount=total_amount,
                shipping_address=shipping_address,
                payment_method=payment_method
            )
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )
        else:
            # Cart order
            cart = get_or_create_cart(user)
            cart_items = cart.cartitem_set.all()
            
            if not cart_items.exists():
                messages.error(request, 'Your cart is empty')
                return redirect('cart')
            
            total_amount = sum(item.get_total() for item in cart_items)
            
            order = Order.objects.create(
                customer=user,
                total_amount=total_amount,
                shipping_address=shipping_address,
                payment_method=payment_method
            )
            
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            
            # Clear cart after order
            cart_items.delete()
        
        messages.success(request, 'Order placed successfully!')
        return redirect('order_details', order_id=order.id)
    
    return redirect('checkout')


def order_details(request, order_id):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    order = get_object_or_404(Order, id=order_id, customer=user)
    
    context = {
        'order': order,
        'user': user,
    }
    return render(request, 'order_details.html', context)


def download_invoice(request, order_id):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    order = get_object_or_404(Order, id=order_id, customer=user)
    
    # Create PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Title
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 50, "INVOICE")
    
    # Order details
    p.setFont("Helvetica", 12)
    y = height - 100
    p.drawString(50, y, f"Order Number: {order.order_number}")
    y -= 20
    p.drawString(50, y, f"Order Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 20
    p.drawString(50, y, f"Customer: {order.customer.username}")
    y -= 20
    p.drawString(50, y, f"Email: {order.customer.email}")
    y -= 30
    
    # Shipping address
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Shipping Address:")
    y -= 20
    p.setFont("Helvetica", 10)
    address_lines = order.shipping_address.split('\n')
    for line in address_lines:
        p.drawString(50, y, line)
        y -= 15
    
    y -= 20
    
    # Items
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Items:")
    y -= 20
    p.setFont("Helvetica", 10)
    
    for item in order.items.all():
        p.drawString(50, y, f"{item.product.name} - Qty: {item.quantity} - Price: ${item.price} each")
        y -= 15
        if y < 100:
            p.showPage()
            y = height - 50
    
    y -= 20
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, f"Total Amount: ${order.total_amount}")
    y -= 20
    p.setFont("Helvetica", 10)
    p.drawString(50, y, f"Payment Method: {order.get_payment_method_display()}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_number}.pdf"'
    return response


def your_orders(request):
    if not is_logged_in(request):
        return redirect('user_login')
    
    user_id = request.session.get('user_id')
    user = Customer.objects.get(id=user_id)
    orders = Order.objects.filter(customer=user).order_by('-order_date')
    
    context = {
        'orders': orders,
        'user': user,
    }
    return render(request, 'your_orders.html', context)
