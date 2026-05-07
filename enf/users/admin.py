from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'country']
    list_filter = ('country', )
    search_fields = ('email', 'first_name', 'last_name', 'company', 'city', 'country')
    ordering = ('email', )
    fieldsets = (
        (None, {
            'fields' : ('email', 'password')}),
        ('Personal Info', {
            'fields' : ('first_name', 'last_name', 'company', 'address1', 'address2', 'city', 'country', 'province', 'postal_code', 'phone')
        }), 
        ('Permissions', {
            'fields'  : ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields' : ('last_login', 'date_joined')
        })
    )

    add_fieldsets = (
        (None, {
            'classes' : ('wide',),
            'fields' : ('email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active',)
        }), 

    )
# Метод гет форм перехватывает момент создания формы и меняет его до того как покажет пользователю
    def get_form(self, request, obj = None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'surname' in form.base_fields:
            form.base_fields['username'].disabled  = True  # Сделать поле username если в форме присутсвует surname 
        
        return form 


