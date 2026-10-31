from django.contrib import admin

from .models import Plan, Product, ProductVariant, TaxRule


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "sales_price", "tax_rule", "is_active")
    search_fields = ("name",)
    inlines = [VariantInline]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "price", "billing_period", "min_quantity", "start_date", "end_date", "is_active")
    list_filter = ("billing_period", "is_active")


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rate", "is_active")
