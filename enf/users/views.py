from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponse
from .forms import CustomUserCreationForm, CustomUserLoginForm, CustomUserUpdateForm
from .models import CustomUser
from django.contrib import messages
from main.models import Product
from django.template.response import TemplateResponse


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend') 
            return redirect('main:index.ml')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', context = {'form':form})
 
def login_view(request):
    if request.method == 'POST':
        form = CustomUserLoginForm(request = request, data = request.POST) # Здесь передаем request = request потому что форма AuthenicationForm требует первым аргументом request
        if form.is_valid():
            user = form.get_user() # Не используем form.save() как в примере выше потому что форма AuthenticationForm ничего не сохраняет а лишь проверяет и кладет пользователя в get_user()
            # В отличии от UserCreationForm которая сохраняет объект пользователя в бд и при form.save() вернет этот объкет.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('main:index')    
    else:
        form = CustomUserLoginForm()
        return render(request, 'users/login.html', {'form' : form})
    
@login_required
def profile_view(request):
    if request.method == 'POST':
        form = CustomUserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            if request.headers.get('HX-Request'):
                return HttpResponse(headers = {'headers' : reverse('users:profile')}) #Здест фронт ждет просто обноволение заголовко, не требуется обновлять всю страницу полностью
            return redirect('users:profile')        
    else:
        form = CustomUserUpdateForm(instance = request.user)
    recommended_products = Product.objects.all().order_by('id')[:3]
    return TemplateResponse(request, 'users/profile.html', context = {
        'form' : form, 
        'user' : request.user, 
        'recommended_products' : recommended_products,
    }) 


@login_required
def account_details(request):
    user = get_user_model().objects.get(id = request.user.id)
    return TemplateResponse(request, 'users/partials/account_details.html', context = {'user':user})

@login_required
def edit_account_details(request):
    form = CustomUserUpdateForm(instance = request.user)
    return TemplateResponse(request, 'users/partials/edit_account_detail.html', context = {'users':request.user, 'form':form})

@login_required
def update_account_details(request):
    if request.method == 'POST':
        form = CustomUserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.clean()
            user.save()
            updated_user = CustomUser.objects.get(id = user.id)
            request.user = updated_user 
            if request.headers.get('HX-Request'):
                return TemplateResponse(request, 'users/partials/account_details.html', context={'user':updated_user})
            return TemplateResponse(request, 'users/partials/account_details.html', context = {'users':updated_user})
        else:
            return TemplateResponse(request, 'users/partials/account_details.html', {'users': request.user, 'form':form})
        
    if request.header.get('HX-Request'):
        return HttpResponse(headers={"HX-Redirect":reverse('users:profile')})
    return redirect("users:profile")

def logout_view(request):
    logout(request)
    if request.headers.get('HX-Request'):
        return HttpResponse(headers={"HX-Redirect": reverse('main:index')})
    return redirect('main:index')