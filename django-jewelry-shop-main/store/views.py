from django.contrib.auth import login
from django.contrib.auth.models import User
from store.models import Address, Blog, Cart, Category, Order, OrderItem, Product, Wishlist
from django.shortcuts import redirect, render, get_object_or_404
from .forms import RegistrationForm, AddressForm
from django.contrib import messages
from django.views import View
import decimal
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator # for Class Based Views
from django.core.mail import send_mail
from jewelryshop import settings
from .utils import *
from datetime import datetime
from django.utils import timezone
import pyotp
import razorpay
from razorpay.errors import BadRequestError,GatewayError,ServerError

# Create your views here.

def home(request):
    categories = Category.objects.filter(is_active=True, is_featured=True)[:3]
    products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    
    if request.method == "POST":
        email = request.POST['email']
        fullmessage = user_full_message(email,"Golden Glamour")
        mail = send_mail(
                'Welcome to Golden Glamour – Thank You for Subscribing! ',
                fullmessage,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=True
            )
        if mail!=None:
            messages.success(request,"Subscribed Successfully..")
            return redirect('store:home')
    
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'store/index.html', context)


def detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.exclude(id=product.id).filter(is_active=True, category=product.category)
    context = {
        'product': product,
        'related_products': related_products,

    }
    return render(request, 'store/detail.html', context)


def all_categories(request):
    categories = Category.objects.filter(is_active=True)
    return render(request, 'store/categories.html', {'categories':categories})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(is_active=True, category=category)
    categories = Category.objects.filter(is_active=True)
    context = {
        'category': category,
        'products': products,
        'categories': categories,
    }
    return render(request, 'store/category_products.html', context)


# Authentication Starts Here

class RegistrationView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'account/register.html', {'form': form})
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'This email is already registered. Please use a different email.')
                return render(request, 'account/register.html', {'form': form})

            # If email is unique, proceed with the registration
            user = form.save(commit=False)
            
            otp = send_otp(request)
            
            subject = f"Let's verify your email, {email}"
            plain_message = verification_full_messgae(user,otp)
            
            request.session['otp'] = otp
            request.session['email'] = email
            
            send_mail(
                subject,
                plain_message,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
                html_message=plain_message  # Send as HTML
            )
            
            user.is_active = False  # Deactivate until OTP is verified
            user.save()
            
            messages.success(request, "OTP sent to your email. Please verify.")
            return redirect('store:otpverification')
        return render(request, 'account/register.html', {'form': form})



def otp_verification(request):
    if request.method == "POST":
        user_otp = request.POST.get('otp')
        email = request.session.get('email')
        otp_secret_key = request.session.get('otp_secret_key')
        otp_valid_date = request.session.get('otp_valid_date')

        if not all([email, otp_secret_key, otp_valid_date]):
            messages.error(request, "Session expired. Please request a new OTP.")
            return redirect('store:register')

        # Check if OTP is still valid
        valid_until = timezone.make_aware(datetime.fromisoformat(otp_valid_date))
        if timezone.now() > valid_until:
            messages.error(request, "OTP has expired. Please request a new one.")
            return redirect('store:register')

        # Verify OTP
        totp = pyotp.TOTP(otp_secret_key, interval=120)
        if totp.verify(user_otp):
            user = get_object_or_404(User, email=email)
            user.is_active = True
            user.save()

            # Clear session
            request.session.flush()

            messages.success(request, "OTP verified successfully. You can now log in.")
            return redirect('store:login')
        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, 'account/otp_verification.html')


def resend_otp(request):
    email = request.session.get('email')
    if not email:
        messages.error(request, "Session expired. Please register again.")
        return redirect('store:register')
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, "No user found for the provided email.")
        return redirect('store:register')

    otp = send_otp(request)

    subject = f"Your new OTP for verification, {email}"
    plain_message = verification_full_messgae(user, otp)

        # Store new OTP
    request.session['otp'] = otp

    send_mail(
            subject,
            plain_message,
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
            html_message=plain_message
    )

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('store:otpverification')



@login_required
def profile(request):
    addresses = Address.objects.filter(user=request.user)
    orders = Order.objects.filter(user=request.user)
    return render(request, 'account/profile.html', {'addresses':addresses, 'orders':orders})


@method_decorator(login_required, name='dispatch')
class AddressView(View):
    def get(self, request):
        form = AddressForm()
        return render(request, 'account/add_address.html', {'form': form})

    def post(self, request):
        form = AddressForm(request.POST)
        if form.is_valid():
            user=request.user
            address = form.cleaned_data['address']
            user_phone_number = form.cleaned_data['user_phone_number']
            city = form.cleaned_data['city']
            state = form.cleaned_data['state']
            pincode = form.cleaned_data['pincode']
            reg = Address(user=user, address=address,user_phone_number=user_phone_number, city=city, state=state,pincode=pincode )
            reg.save()
            messages.success(request, "New Address Added Successfully.")
        return redirect('store:profile')


@login_required
def remove_address(request, id):
    a = get_object_or_404(Address, user=request.user, id=id)
    a.delete()
    messages.success(request, "Address removed.")
    return redirect('store:profile')


@login_required
def add_to_cart(request):
    user = request.user
    product_id = request.GET.get('prod_id')
    product = get_object_or_404(Product, id=product_id)

    # Check whether the Product is alread in Cart or Not
    item_already_in_cart = Cart.objects.filter(product=product_id, user=user)
    if item_already_in_cart:
        cp = get_object_or_404(Cart, product=product_id, user=user)
        cp.quantity += 1
        cp.save()
    else:
        Cart(user=user, product=product).save()
    
    return redirect('store:cart')


def get_cart_amount_and_order_data(user):
 
    amount = decimal.Decimal(0)
    shipping_amount = decimal.Decimal(99)
    
    cp = [p for p in Cart.objects.all() if p.user == user]
    if cp:
        for p in cp:
            temp_amount = (p.quantity * p.product.price)
            amount += temp_amount
  
    return amount, shipping_amount


@login_required
def cart(request):
    user = request.user
    cart_products = Cart.objects.filter(user=user)
    
    amount, shipping_amount = get_cart_amount_and_order_data(user)

    addresses = Address.objects.filter(user=user)
        
    context = {
        'cart_products': cart_products,
        'amount': amount,
        'shipping_amount': shipping_amount,
        'total_amount': amount + shipping_amount,
        'addresses': addresses,
    }
    
    return render(request, 'store/cart.html', context)

    
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
def generate_payment(request):
    if request.method == "POST":
        user = request.user
        cart_products = Cart.objects.filter(user=user)

        # Get selected address
        address_id = request.POST.get("address")
        if not address_id:
            messages.warning(request, "Please select a shipping address.")
            return redirect("store:cart")

        address = get_object_or_404(Address, id=address_id)

        # Calculate the amount (including shipping, etc.)
        amount, shipping_amount = get_cart_amount_and_order_data(user)
        total_amount_paisa = int((amount + shipping_amount) * 100)  # Convert to paise

        # client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            # Create the Razorpay order
            razorpay_payment = client.order.create({
                "amount": total_amount_paisa,
                "currency": "INR",
                "payment_capture": '1'  # Auto-capture payment
            })
            print(razorpay_payment)
            razorpay_order_id = razorpay_payment["id"]
            
            # Create order records for each cart item
            for item in cart_products:
                order = Order.objects.create(
                user=user,
                address=address,
                product=item.product,
                quantity=item.quantity,
                shipping_charge=shipping_amount,
                razorpay_order_id=razorpay_order_id,
                payment_method="Online",  # or COD based on form input
            )
                order.save()
                
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            # Clear the cart after successful order creation
            cart_products.delete()

        except (BadRequestError,GatewayError,ServerError) as e:
            messages.error(request, f"Payment error: {str(e)}")
            return redirect("store:cart")

        # Pass payment details to template
        context = {
            "razorpay_key": settings.RAZORPAY_KEY_ID,
            "pay_amount": total_amount_paisa,
            "order_id": razorpay_order_id,
            'user': user
        }
    return render(request, "store/payment.html", context) 


 
@csrf_exempt
def payment_success(request):
    if request.method == "POST":
        try:
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')

            print(f"Received Data - Payment ID: {razorpay_payment_id}, Order ID: {razorpay_order_id}, Signature: {razorpay_signature}")

            # Ensure all required parameters are present
            if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
                print("Error: Missing payment data!")  # Debugging
                messages.error(request, "Invalid payment data received!")
                return redirect("store:cart")

            # Verify the payment signature
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }

            print("Verifying signature...")
            client.utility.verify_payment_signature(params_dict)
            print("Signature verified successfully!")

            # Update Order in Database
            order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
            payment_method = request.POST.get('payment_method', 'Online')

            if order:
                login(request, order.user)
                print(f"Order Found: {order.id}") 
                order.razorpay_payment_id = razorpay_payment_id
                order.razorepay_payment_signature = razorpay_signature  
                order.payment_method = payment_method
                order.payment_status = "PrePaid"
                order.save()
                print("Order saved successfully!")  

                messages.success(request,"Payment successful! 🎉")
                messages.success(request, "Your order has been successfully placed!")
                send_order(order,razorpay_order_id)
                messages.success(request,"An order confirmation email has been sent to your registered email.")
                return render(request, 'store/success.html')

            print("Error: Order not found!")  
            messages.error(request, "Order not found. Please contact support.")
            return redirect("store:cart")

        except razorpay.errors.SignatureVerificationError:
            print("Error: Razorpay Signature Verification Failed.")  
            messages.error(request, "Razorpay Signature Verification Failed.")
            return redirect("store:cart")

        except Exception as e:
            print(f"Error: {str(e)}") 
            messages.error(request, f"Error: {str(e)}")
            return redirect("store:cart")

    print("Invalid request method, redirecting to cart...")  
    return redirect("store:cart")



@login_required
def remove_cart(request, cart_id):
    if request.method == 'GET':
        c = get_object_or_404(Cart, id=cart_id)
        c.delete()
        messages.error(request, "🛒 Product removed from cart.")
    return redirect('store:cart')


@login_required
def plus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        cp.quantity += 1
        cp.save()
    return redirect('store:cart')


@login_required
def minus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        # Remove the Product if the quantity is already 1
        if cp.quantity == 1:
            cp.delete()
        else:
            cp.quantity -= 1
            cp.save()
    return redirect('store:cart')


@login_required
def checkout(request):
    if request.method == "POST":
        user = request.user
        cart_products = Cart.objects.filter(user=user)

        # Get selected address
        address_id = request.POST.get("address")
        if not address_id:
            messages.warning(request, "Please select a shipping address.")
            return redirect("store:cart")

        address = get_object_or_404(Address, id=address_id)

        # Calculate the amount (including shipping, etc.)
        amount, shipping_amount = get_cart_amount_and_order_data(user)

        payment_method = request.POST.get('payment_method', 'Online')   
        # Create order records for each cart item
        for item in cart_products:
            order = Order.objects.create(
                user=user,
                address=address,
                product=item.product,
                quantity=item.quantity,
                shipping_charge=shipping_amount,
                payment_method=payment_method,  # or COD based on form input
            )
            order.save()
                
            OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            # Clear the cart after successful order creation
            cart_products.delete()
        messages.success(request, f"Order placed successfully with {payment_method} method.")
        return redirect('store:orders')  

    return redirect('store:cart')


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order , id=order_id)
    
    if order_id=='Delivered':
        messages.error(request, "You cannot cancel a delivered order.")
        return redirect('store:orders')
        
    order.status = 'Cancelled'
    order.save()
    messages.error(request, "Your order has been cancelled.")
    return redirect('store:orders')



@login_required
def orders(request):
    all_orders = Order.objects.filter(user=request.user).order_by('-ordered_date')
    return render(request, 'store/orders.html', {'orders': all_orders})


@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)

    if created:
        messages.success(request, "❤️ Product added to your wishlist!")
        return redirect('store:wishlist') 
    else:
        wishlist_item.delete()
        messages.warning(request, "❌ Product removed from your wishlist!")

    return redirect(request.META.get('HTTP_REFERER', 'store:wishlist'))


@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user)
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def track_order(request):
    order = None
    searched = False
    tracking_steps = ['Pending', 'Accepted', 'Packed', 'On The Way','Out For Delivery','Delivered']
    current_index = 0

    if request.method == 'POST':
        tracking_uid = request.POST.get('tracking_id')
        try:
            order = Order.objects.get(tracking_uid=tracking_uid)
            if order.status in tracking_steps:
                current_index = tracking_steps.index(order.status)
        except Order.DoesNotExist:
            order = None
        searched = True

    return render(request, 'store/track_order.html', {
        'order': order,
        'searched': searched,
        'tracking_steps': tracking_steps,
        'current_index': current_index,
    })

@login_required
def track_order_direct(request, tracking_id):
    order = Order.objects.filter(tracking_id=tracking_id).first()
    searched = True  # For template condition

    tracking_steps = ["Pending", "Accepted", "Packed", "On The Way","Out For Delivery", "Delivered"]
    current_index = tracking_steps.index(order.status) if order and order.status in tracking_steps else 0

    return render(request, 'store/track_order.html', {
        'order': order,
        'searched': searched,
        'tracking_steps': tracking_steps,
        'current_index': current_index
    })
    

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        
        subject = f'New Inquiry from {name} via Golden Glamour Contact Page'
        message = (
            f"Dear Admin,\n\n"
            f"You have received a new message from the contact form on your website.\n\n"
            f"Sender Name: {name}\n"
            f"Sender Email: {email}\n\n"
            f"Message:\n{message}\n\n"
            f"Best Regards,\n"
            f"Golden Glamour Website"
        )
        # Example email logic
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
        messages.success(request, "Thank you for contacting us. Your message has been successfully sent. We’ll get back to you shortly.")

    return render(request, 'contact.html')

def blog_list(request):
    blogs = Blog.objects.order_by('-date')
    return render(request, 'blog.html', {'blogs': blogs})


def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    return render(request, 'blog_detail.html', {'blog': blog})

def shop(request):
    return render(request, 'store/shop.html')


def test(request):
    return render(request, 'store/test.html')




