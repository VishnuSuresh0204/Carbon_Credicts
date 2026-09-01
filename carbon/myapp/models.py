from django.db import models
from django.contrib.auth.models import AbstractUser
 
 
class Login(AbstractUser):
    usertype = models.CharField(max_length=50)
    viewpassword = models.CharField(max_length=100, blank=True)
 
    def __str__(self):
        return self.username
 
 
class Organization(models.Model):
    login = models.OneToOneField(Login, on_delete=models.CASCADE)
    organization_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    industry_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return self.organization_name


# ============================================================
# EMISSION RECORD
# ============================================================

class EmissionRecord(models.Model):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )

    electricity_consumption = models.FloatField()

    fuel_consumption = models.FloatField()

    transportation_distance = models.FloatField()

    production_level = models.FloatField()

    total_emission = models.FloatField()

    status = models.CharField(
        max_length=30,
        default="Pending"
    )
    # Pending / Verified / Rejected

    recorded_date = models.DateField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.organization} - {self.recorded_date}"


# ============================================================
# ML EMISSION PREDICTION
# ============================================================

class EmissionPrediction(models.Model):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE
    )

    electricity_consumption = models.FloatField()

    fuel_consumption = models.FloatField()

    transportation_distance = models.FloatField()

    production_level = models.FloatField()

    predicted_emission = models.FloatField()

    prediction_date = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.organization} - "
            f"{self.predicted_emission} tonnes"
        )