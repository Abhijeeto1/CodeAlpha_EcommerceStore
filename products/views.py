
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from decimal import Decimal

from .models import Product, Order, OrderItem


# HOME PAGE
def home(request):
    products = Product.objects.all()

    search_query = request.GET.get('search', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)

    selected_category = request.GET.get('category', '').strip()

    if selected_category:
        products = products.filter(category=selected_category)

    return render(request, 'home.html', {
        'products': products,
        'search_query': search_query,
        'selected_category': selected_category,
    })


# PRODUCT DETAILS
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    return render(request, 'product_detail.html', {
        'product': product
    })


# ADD PRODUCT TO CART
def add_to_cart(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)

        cart = request.session.get('cart', {})
        product_id = str(product.id)

        current_quantity = int(cart.get(product_id, 0))

        if current_quantity < product.stock:
            cart[product_id] = current_quantity + 1
            request.session['cart'] = cart
            messages.success(request, 'Product added to cart!')
        else:
            messages.error(request, 'Insufficient stock!')

    return redirect('cart')


# CART PAGE
def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = Decimal('0.00')
    total_quantity = 0

    for product_id, quantity in cart.items():
        product = Product.objects.filter(pk=product_id).first()

        if product:
            quantity = int(quantity)
            subtotal = product.price * quantity

            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })

            total += subtotal
            total_quantity += quantity

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total,
        'total_quantity': total_quantity
    })


# REMOVE PRODUCT FROM CART
def remove_from_cart(request, pk):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        cart.pop(str(pk), None)
        request.session['cart'] = cart

        messages.success(request, 'Product removed from cart.')

    return redirect('cart')


# UPDATE CART QUANTITY
def update_cart(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        cart = request.session.get('cart', {})

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid quantity.')
            return redirect('cart')

        if quantity <= 0:
            cart.pop(str(pk), None)
            messages.success(request, 'Product removed from cart.')

        elif quantity <= product.stock:
            cart[str(pk)] = quantity
            messages.success(request, 'Cart updated successfully.')

        else:
            messages.error(
                request,
                f'Only {product.stock} items are available.'
            )

        request.session['cart'] = cart

    return redirect('cart')


# CHECKOUT PAGE AND ORDER PROCESSING
def checkout(request):
    cart = request.session.get('cart', {})

    if not cart:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    cart_items = []
    total = Decimal('0.00')
    total_quantity = 0

    # Prepare cart details for checkout page
    for product_id, quantity in cart.items():
        product = Product.objects.filter(pk=product_id).first()

        if product:
            quantity = int(quantity)
            subtotal = product.price * quantity

            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })

            total += subtotal
            total_quantity += quantity

    if not cart_items:
        messages.error(request, 'No valid products found in your cart.')
        return redirect('cart')

    # Process order after form submission
    if request.method == 'POST':

        customer_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        payment_method = request.POST.get('payment_method', 'COD')

        if not all([
            customer_name,
            phone,
            email,
            address,
            city,
            pincode
        ]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('checkout')

        if payment_method != 'COD':
            messages.error(request, 'Invalid payment method.')
            return redirect('checkout')

        try:
            with transaction.atomic():

                order_products = []
                order_total = Decimal('0.00')

                # Verify stock and calculate final order total
                for product_id, quantity in cart.items():

                    quantity = int(quantity)

                    if quantity <= 0:
                        raise ValueError('Invalid product quantity.')

                    product = Product.objects.select_for_update().filter(
                        pk=product_id
                    ).first()

                    if not product:
                        raise ValueError('A product is no longer available.')

                    if quantity > product.stock:
                        raise ValueError(
                            f'Only {product.stock} units of '
                            f'{product.name} are available.'
                        )

                    order_total += product.price * quantity
                    order_products.append((product, quantity))

                # Create order
                order = Order.objects.create(
                    customer_name=customer_name,
                    phone=phone,
                    email=email,
                    address=address,
                    city=city,
                    pincode=pincode,
                    payment_method='COD',
                    total_amount=order_total
                )

                # Create order items and update stock
                for product, quantity in order_products:

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price
                    )

                    product.stock -= quantity
                    product.save(update_fields=['stock'])

                # Clear cart after successful order
                request.session.pop('cart', None)

            messages.success(request, 'Your order has been placed successfully!')

            return redirect('order_success', order_id=order.id)

        except (ValueError, TypeError, Product.DoesNotExist) as error:
            messages.error(request, str(error))
            return redirect('cart')

    # Display checkout page
    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'total_quantity': total_quantity
    })


# ORDER SUCCESS PAGE
def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    return render(request, 'order_success.html', {
        'order': order
    })
