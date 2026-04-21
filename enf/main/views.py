from django.shortcuts import render, get_object_or_404, get_list_or_404
from django.views.generic import TemplateView, DetailView
from django.http import HttpResponse
from django.template.response import TemplateResponse
from .models import Category, Product, Size 
from django.db.models import Q


class IndexView(TemplateView):
    template_name = 'main/base.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = None
        return context 
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get('HX-Request'):
            return TemplateResponse(request, 'main/home_content.html', context)
        return TemplateResponse(request, self.template_name, context)

class CatalogView(TemplateView):
    template_name = 'main/base.html'

    FILTER_MAPPING = {
        'color' : lambda queryset, value : queryset.filter(color__iexact = value),
        'min_price' : lambda queryset, value : queryset.filter(price__gte = value),
        'max_price' : lambda queryset, value : queryset.filter(price__lte = value),
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = kwargs.get('category_slug') 
        categories = Category.objects.all() 
        products = Product.objects.all().order_by('-created_at') 
        current_category = None  

        if category_slug:
            current_category = get_object_or_404(Category, slug = category_slug)
            products = products.filter(category = current_category)
        querry = self.request.GET.get('q')                                                               # Сохарняем запрос фильтра в переменную    querry
        if querry:                                                                                       # Если есть такой запрос то показываем товары по нему
            products = products.filter(Q(name__icontains = querry) | Q(description__icontains = querry))
        
        filter_params = {}                                                                               # Это словарь для отображения фильтров
        for param, filter_func in self.FILTER_MAPPING.items():
            value = self.request.GET.get(param)
            if value:
                products = filter_func(products, value)
                filter_params[param] = value                                                             # Если мы нашли что то по фильтрации то обновляем словарь фильтров
            else:
                filter_params[param] = ''                                                                # Если нет то пустое 
        filter_params['q'] = querry or ''
                                                                                                         # Если есть запрос филтьтра то его тоже сохраним в словарь филтров 
        context.update({ 
            'categories' : categories,
            'products' : products, 
            'current_category' : current_category, 
            'filter_params' : filter_params, 
            'sizes' : Size.objects.all(),
            'search_querry' : querry or ''                                                               # Отображаем сам запрос в шаблонах 
        })

        if self.request.GET.get('show_search') == 'true':                                                  # Отделение поиска от обычного католога 
            context['show_search'] = True 
        elif self.request.GET.get('reset_search') == 'true':
            context['reset_search'] = True

        return context 
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if request.headers.get('HX-Request'):
            if context.get('show-search'):
                return TemplateResponse(request, "main/search_input.html", context)
            elif context.get('reset_search'):
                return TemplateResponse(request, "main/search_button.html", {})
            template = "main/filter_modal.html" if request.GET.get("show_filters") == 'true' else "main/catalog.html"
            return TemplateResponse(request, template, context )
        return TemplateResponse(request, self.template_name, context )
    
class ProductDetailView(DetailView):
    model = Product
    template_name = 'main/base.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        context['categories'] = Category.objects.all()
        context['related_products'] = Product.objects.filter(
            category=product.category
        ).exclude(id=product.id)[:4]
        context['current_category'] = product.category.slug
        return context
    

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(**kwargs)
        if request.headers.get('HX-Request'):
            return TemplateResponse(request, 'main/product_detail.html', context)
        return TemplateResponse(request, self.template_name, context)
