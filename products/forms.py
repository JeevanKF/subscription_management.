"""products/forms.py"""
from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Plan, Product, ProductVariant, TaxRule


class TaxRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxRule
        fields = ["name", "rate", "is_active"]


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "product_type", "sales_price", "cost_price", "tax_rule", "notes", "is_active"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer active tax rules, but keep the current one if it was deactivated
        taxes = TaxRule.objects.filter(is_active=True)
        if self.instance.tax_rule_id:
            taxes = taxes | TaxRule.objects.filter(pk=self.instance.tax_rule_id)
        self.fields["tax_rule"].queryset = taxes


class VariantForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["attribute", "value", "extra_price"]


class BaseVariantFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            key = (form.cleaned_data.get("attribute", "").strip().lower(),
                   form.cleaned_data.get("value", "").strip().lower())
            if all(key):
                if key in seen:
                    form.add_error("value", "This variant already exists.")
                seen.add(key)


VariantFormSet = forms.inlineformset_factory(
    Product, ProductVariant,
    form=VariantForm, formset=BaseVariantFormSet,
    extra=2, can_delete=True,
)


class PlanForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            "name", "product", "price", "billing_period", "min_quantity",
            "start_date", "end_date",
            "auto_close", "closable", "pausable", "renewable", "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "min_quantity": forms.NumberInput(attrs={"min": "1"}),
        }
