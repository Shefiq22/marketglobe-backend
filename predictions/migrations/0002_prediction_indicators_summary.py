from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("predictions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prediction",
            name="indicators",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="prediction",
            name="summary",
            field=models.TextField(blank=True, default=""),
        ),
    ]
