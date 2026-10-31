from django.contrib import admin

from .models import QuotationTemplate, Subscription, SubscriptionLine, SubscriptionStatusChange, TemplateLine


class SubscriptionLineInline(admin.TabularInline):
    model = SubscriptionLine
    extra = 0


class StatusChangeInline(admin.TabularInline):
    model = SubscriptionStatusChange
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "changed_by", "reason", "changed_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "plan", "status", "start_date", "expiry_date", "next_billing_date"]
    list_filter = ["status", "plan"]
    search_fields = ["number", "customer__name", "customer__email"]
    readonly_fields = ["number", "status"]   # status only changes through services.py
    inlines = [SubscriptionLineInline, StatusChangeInline]


class TemplateLineInline(admin.TabularInline):
    model = TemplateLine
    extra = 0


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "plan", "validity_days", "duration_months", "is_active"]
    inlines = [TemplateLineInline]
