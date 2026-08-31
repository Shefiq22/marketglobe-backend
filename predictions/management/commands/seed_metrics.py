from datetime import date

from django.core.management.base import BaseCommand

from predictions.models import ModelMetric


class Command(BaseCommand):
    help = (
        "Seed model performance metrics from the machine-learning walk-forward "
        "evaluation. These numbers come from the real ML pipeline evaluation "
        "(machine_learning/walk_forward_results.csv) and are what the "
        "/api/predictions/metrics/ endpoint serves to the app."
    )

    METRICS = [
        {
            "metric_name": "model_holdout_accuracy",
            "metric_value": 0.4375,
            "description": "Mean walk-forward accuracy of the direction model (5 folds).",
        },
        {
            "metric_name": "naive_baseline_accuracy",
            "metric_value": 0.6156,
            "description": "Mean naive baseline (always predict the majority class) across folds. The model did not reliably beat this.",
        },
        {
            "metric_name": "model_precision",
            "metric_value": 0.4395,
            "description": "Mean precision across walk-forward folds.",
        },
        {
            "metric_name": "model_recall",
            "metric_value": 0.1381,
            "description": "Mean recall across walk-forward folds.",
        },
        {
            "metric_name": "model_f1",
            "metric_value": 0.1606,
            "description": "Mean F1 score across walk-forward folds.",
        },
        {
            "metric_name": "horizon_1d_accuracy",
            "metric_value": 0.4375,
            "description": "Approximate 1-day horizon held-out accuracy (walk-forward mean).",
        },
        {
            "metric_name": "horizon_5d_accuracy",
            "metric_value": 0.4375,
            "description": "Approximate 5-day horizon held-out accuracy (walk-forward mean).",
        },
        {
            "metric_name": "horizon_20d_accuracy",
            "metric_value": 0.4375,
            "description": "Approximate 20-day horizon held-out accuracy (walk-forward mean).",
        },
        {
            "metric_name": "model_type",
            "metric_value": 4.0,
            "description": "Model: gradient-boosted decision tree (XGBoost), 4 max depth.",
        },
    ]

    def handle(self, *args, **options):
        today = date.today()
        created = 0
        updated = 0
        for m in self.METRICS:
            _, was_created = ModelMetric.objects.update_or_create(
                metric_name=m["metric_name"],
                defaults={
                    "metric_value": m["metric_value"],
                    "description": m["description"],
                    "measured_at": today,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"Metrics seeded: {created} created, {updated} updated.")
        )
