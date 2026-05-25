from django.shortcuts import render
import stripe
import requests
from django.conf import settings
from django.shortcuts import redirect, get_list_or_404, render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.template.response import TemplateResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from orders.models import Order 
from cart.views import CartMixin


# Create your views here.
# stripe login 
# stripe listen --forward-to localhost:8000/payment/stripe/webhook/


stripe.api_key = settings.STRIPE_SECRET_KEY
stripe_endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

def create_stripe_checkout_session(order, request):
    """
    Метод для создания платежной сессии
    Получаем корзину
    Создаем массив данных который принимает Stripe - line_items
    Через try создаем сессию оплаты.
    Сохраняем данные о заказе.
    """
    cart = CartMixin().get_cart(request)
    line_items = []
    for item in cart.items.select_related('product', 'product_size'):
        line_items.append({
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': f'{item.product.name} - {item.product_size.size.name}',
                },
                'unit_amount': int(item.product.price * 100),
            },
            'quantity': item.quantity,
        })
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri('/payment/stripe/success/') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri('/payment/stripe/cancel/') + f'?order_id={order.id}',
            metadata={
                'order_id': order.id
            }
        )
        order.stripe_payment_intent_id = checkout_session.payment_intent
        order.payment_provider = 'stripe'
        order.save()
        return checkout_session
    except Exception as e:
        raise
@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    @csrf_exempt - Страйп не знает нашег CSRF Token, @require_POST - ограничение только на отправку данных со стороны страйпа.
    Получаем Payload - данные о платеже 
    Получаем подпись от страйпа - Захеширолванные данные WebhookSecret+Payload
    construct_event - проверка подписи, джанго выолняет такое же хеишрование данных если результат такой же то возвращается объект сессии 
    Получаем платежную сессию из данных
    Сохраняем данные о заказе
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_endpoint_secret
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificartionError as e:
        return HttpResponse(status=400)
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.metadata.order_id
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'processing'
            order.stripe_payment_id = session.payment_intent
            order.save()
        except Order.DoesNotExist:
            return HttpResponse(status=400)
        
    return HttpResponse(status=200)

def stripe_success(request):
    """
    Получаем ID cecсии из строки success_url = request.build_absolute_uri('payment/stripe/sussecc/') + '?/session_id={CHECKOUT_SESSION_ID}',
    Метод retirve запрашивает информацию по плетжной сессии от Stripe на основе session_id (CHECKOUT_SESSION_ID Stripe заменил этот параметр на ID)
    Из информации по сессии достаем айди заказа
    Дастаем заказ из сессии для передачи в контекст 
    Очищаем коризну
    """
  
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            order_id = session.metadata.order_id
            order = get_object_or_404(Order, id=order_id)

            cart = CartMixin().get_cart(request)
            cart.clear()

            context = {'order': order}
            if request.headers.get('HX-Request'):
                return TemplateResponse(request, 'payment/stripe_success_content.html', context)
            return render(request, 'payment/stripe_success.html', context)
        except Exception as e:
            raise
    return redirect('main:index')


def stripe_cancel(request): 
    """
    Получаем order_id из cancel_url = request.build_absolute_uri('/payment/stripe/cancel/') + f'order_id={order.id}',
    Далее по order_id получаем заказ и меняем его статус, сохраняем все, рендерим соответствующие страницы.
    """
    order_id = request.GET.get('order_id')
    if order_id:
        order = get_object_or_404(Order, id=order_id)
        order.status = 'cancelled'
        order.save()
        context = {'order': order}
        if request.headers.get('HX-Request'):
            return TemplateResponse(request, 'payment/stripe_cancel_content.html', context)
        return render(request, 'payment/stripe_cancel.html', context)
    return redirect('orders:checkout')
