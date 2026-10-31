import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
        # subscriptions points a ForeignKey at Variant, so it must exist before the rename
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(old_name="Variant", new_name="ProductVariant"),
        migrations.RenameField(model_name="product", old_name="description", new_name="notes"),
        migrations.AddField(
            model_name="productvariant",
            name="attribute",
            field=models.CharField(default="", help_text="e.g. Brand", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="productvariant",
            name="value",
            field=models.CharField(default="", help_text="e.g. Odoo", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="productvariant",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="taxrule",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plan",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
