
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import View
from django.http import JsonResponse, HttpResponse
from django.template.response import TemplateResponse
from django.contrib import messages
from django.db import transaction
from main.models import Product, ProductSize
from .models import Cart, CartItem
from .forms import AddToCartForm
import json


class CartMixin:
    """
    Миксин нужен для быстрого получения корзины из любого класса представления.
    Миксин проверяет есть ли уже корзина в request.cart (из middleware) если есть то вернет 
    Проверка есть ли у пользователя session_key если нет то создает 
    Поиск или создание корзины на основе session_key
    Сохраняет cart.id в сессию для быстрого поиска в бд
    """
    def get_cart(self, request):
        if hasattr(request, 'cart'):
            return request.cart
    
        if not request.session.session_key:
            request.session.create()

        cart, created = Cart.objects.get_or_create(
            session_key=request.session.session_key
        )

        request.session['cart_id'] = cart.id
        request.session.modified = True
        return cart
    

class CartModalView(CartMixin, View):
    """
    Метод получаем корзину и передает в контест шаблона данные о товарах
    """
    def get(self, request):
        cart = self.get_cart(request)
        context = {
            'cart': cart,
            'cart_items': cart.items.select_related(
                'product',
                'product_size__size'
            ).order_by('-added_at')
        }
        return TemplateResponse(request, 'cart/cart_modal.html', context)


class AddToCartView(CartMixin, View):
    """
    Метод добавляет товар в корзину в рамках одной транзакции
    Получаем коризну и товар
    Заполняем форму добавления товара
    Выбираем размер, если пользователь ввел размер то достаем его если нет то берем первый из бд
    Проверяем чтобы выбранное кол-во было меньше product_size.stock если нет то выдаем ошибку 
    if existing_item: - Проверка на то есть ли товар уже в коризне если да то увлеличиваем его qunatity но чтобы было меньше стока
    """
    @transaction.atomic 
    def post(self, request, slug):
        cart = self.get_cart(request)
        product = get_object_or_404(Product, slug=slug)

        form = AddToCartForm(request.POST, product=product)

        if not form.is_valid():
            return JsonResponse({
                'error': 'Invalid form data',
                'errors': form.errors,
            }, status=400)
        
        size_id = form.cleaned_data.get('size_id')
        if size_id:
            product_size = get_object_or_404(
                ProductSize,
                id=size_id,
                product=product
            )
        else:
            product_size = product.product_sizes.filter(stock__gt=0).first()
            if not product_size:
                return JsonResponse({
                    'error': 'No sizes available'
                }, status=400)

        quantity = form.cleaned_data['quantity']
        if product_size.stock < quantity:
            return JsonResponse({
                'error': f'Only {product_size.stock} items available'
            }, status=400)

        existing_item = cart.items.filter(
            product=product,
            product_size=product_size,
        ).first()

        if existing_item:
            total_quantity = existing_item.quantity + quantity
            if total_quantity > product_size.stock:
                return JsonResponse({
                    'error': f"Cannot add {quantity} items. Only {product_size.stock - existing_item.quantity} more available."
                }, status=400)
            
        cart_item = cart.add_product(product, product_size, quantity)


        if request.headers.get('HX-Request'):
            return redirect('cart:cart_modal')
        else:
            return JsonResponse({
                'success': True,
                'total_items': cart.total_items,
                'message': f"{product.name} added to cart",
                'cart_item_id': cart_item.id
            })
        

class UpdateCartItemView(CartMixin, View):
    """
    Метод обновления товаров в корзине (не связан с методом модели). 
    cart_item - Достаем объект CartItem (коризна + товар)
    Обновляем количество если kwargs пуст то +1
    Если количество меньше 0 - ошибка
    Если 0 то удаляем 
    Если больше стока - ошибка

    """
    @transaction.atomic
    def post(self, request, item_id):
        cart = self.get_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)

        quantity = int(request.POST.get('quantity', 1))

        if quantity < 0:
            return JsonResponse({'error': 'Invalid quantity'}, status=400)
        
        if quantity == 0:
            cart_item.delete()
        else:
            if quantity > cart_item.product_size.stock:
                return JsonResponse({
                    'error': f'Only {cart_item.product_size.stock} items available'
                }, status=400)
            
            cart_item.quantity = quantity
            cart_item.save()

        context = {
            'cart': cart,
            'cart_items': cart.items.select_related(
                'product',
                'product_size__size',
            ).order_by('-added_at')
        }
        return TemplateResponse(request, 'cart/cart_modal.html', context)
    

class RemoveCartItemView(CartMixin, View):
    """
    Удаление товара из коризны то есть удаление CartItem Объекта
    Получаем корзину, есть item_id - id объекта конкретной корзины + конкретного товара.
    Через cart related_name получаем этот объект и удаляем его
    Передаем в контекст остатки товаров.
    """
    def post(self, request, item_id):
        cart = self.get_cart(request)

        try:
            cart_item = cart.items.get(id=item_id)
            cart_item.delete()

            context = {
                'cart': cart,
                'cart_items': cart.items.select_related(
                    'product',
                    'product_size__size',
                ).order_by('-added_at')
            }
            return TemplateResponse(request, 'cart/cart_modal.html', context)
        except CartItem.DoesNotExist:
            return JsonResponse({'error': 'Item not found'}, status=400)
        
    
class CartCountView(CartMixin, View):
    """
    Получение общего кол-ва товаров корзины и общая сумма 
    """
    def get(self, request):
        cart = self.get_cart(request)
        return JsonResponse({
            'total_items': cart.total_items,
            'subtotal': float(cart.subtotal)
        })
    

class ClearCartView(CartMixin, View):
    """
    Класс связанный с методом модели clear. Удаляет все товары корзины.
    """
    def post(self, request):
        cart = self.get_cart(request)
        cart.clear()

        if request.headers.get('HX-Request'):
            return TemplateResponse(request, 'cart/cart_empty.html', {
                'cart': cart
            })
        return JsonResponse({
            'succes': True,
            'message': 'Cart cleared'
        })


class CartSummaryView(CartMixin, View):
    """
    Информация по всем продукатм коризны.
    """
    def get(self, request):
        cart = self.get_cart(request)
        context = {
            'cart': cart,
            'cart_items': cart.items.select_related(
                'product',
                'product_size__size'
            ).order_by('-added_at')
        }
        return TemplateResponse(request, 'cart/cart_summary.html', context)
