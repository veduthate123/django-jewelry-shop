from datetime import timedelta
from django.utils import timezone

import uuid
from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Address(models.Model):
    user = models.ForeignKey(User, verbose_name="User", on_delete=models.CASCADE)
    address = models.TextField(default="")
    user_phone_number = models.CharField(max_length=10,default="")
    city = models.CharField(max_length=100,default="")
    state = models.CharField(max_length=100,default="")
    pincode = models.CharField(max_length=10,default="") 

    def __str__(self):
        return self.address


class Category(models.Model):
    title = models.CharField(max_length=50, verbose_name="Category Title")
    slug = models.SlugField(max_length=55, verbose_name="Category Slug")
    description = models.TextField(blank=True, verbose_name="Category Description")
    category_image = models.ImageField(upload_to='category', blank=True, null=True, verbose_name="Category Image")
    is_active = models.BooleanField(verbose_name="Is Active?")
    is_featured = models.BooleanField(verbose_name="Is Featured?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ('-created_at', )

    def __str__(self):
        return self.title


class Product(models.Model):
    title = models.CharField(max_length=150, verbose_name="Product Title")
    slug = models.SlugField(max_length=160, verbose_name="Product Slug")
    sku = models.CharField(max_length=255, unique=True, verbose_name="Unique Product ID (SKU)")
    short_description = models.TextField(verbose_name="Short Description")
    detail_description = models.TextField(blank=True, null=True, verbose_name="Detail Description")
    product_image = models.ImageField(upload_to='product', blank=True, null=True, verbose_name="Product Image")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(Category, verbose_name="Product Categoy", on_delete=models.CASCADE)
    is_active = models.BooleanField(verbose_name="Is Active?")
    is_featured = models.BooleanField(verbose_name="Is Featured?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")

    class Meta:
        verbose_name_plural = 'Products'
        ordering = ('-created_at', )

    def __str__(self):
        return self.title


class Cart(models.Model):
    user = models.ForeignKey(User, verbose_name="User", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantity")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")
      

    def __str__(self):
        return str(self.user)
    
    # Creating Model Property to calculate Quantity x Price
    @property
    def total_price(self):
        return self.quantity * self.product.price


STATUS_CHOICES = (
    ('Pending', 'Pending'),
    ('Accepted', 'Accepted'),
    ('Packed', 'Packed'),
    ('On The Way', 'On The Way'),
    ('Out For Delivery', 'Out For Delivery'),
    ('Delivered', 'Delivered'),
    ('Cancelled', 'Cancelled')
)

class Order(models.Model):
    PAYMENT_METHODS = [
        ('COD', 'Cash on Delivery'),
        ('Online', 'Online Payment'),
    ]
    
    user = models.ForeignKey(User, verbose_name="User", on_delete=models.CASCADE)
    address = models.ForeignKey(Address, verbose_name="Shipping Address", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Product", on_delete=models.CASCADE, blank=True, null=True)
    quantity = models.PositiveIntegerField(verbose_name="Quantity", blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Amount",default=0)   
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=99.00)  
    ordered_date = models.DateTimeField(auto_now_add=True, verbose_name="Ordered Date")
    razorpay_order_id = models.CharField(max_length=100,null=True,blank=True)
    razorpay_payment_id = models.CharField(max_length=100,null=True,blank=True)
    razorepay_payment_signature = models.CharField(max_length=100,null=True,blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='COD')  # New field
    payment_status = models.CharField(max_length=20, default='Pending')  # Optional field
    tracking_uid = models.CharField(max_length=100, unique=True, blank=True, null=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


    status = models.CharField(
        choices=STATUS_CHOICES,
        max_length=50,
        default="Pending"
        )
    
    
    def __str__(self):
        return f"{self.user} - {self.product} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.tracking_uid:
            self.tracking_uid = str(uuid.uuid4()).replace('-', '')[:10]
            
        if not self.estimated_delivery:
            self.estimated_delivery = self.ordered_date + timedelta(days=6) if self.ordered_date else timezone.now() + timedelta(days=6)
            
        if self.product and self.quantity:
            self.amount = self.quantity * self.product.price
        else:
            self.amount = 0
        super().save(*args, **kwargs)
        
        
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"