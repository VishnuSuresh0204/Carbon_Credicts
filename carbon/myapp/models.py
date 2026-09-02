from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator


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

    class Meta:
        ordering = ["organization_name"]

    def __str__(self):
        return self.organization_name


class EmissionRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    electricity_consumption = models.FloatField(validators=[MinValueValidator(0)])
    fuel_consumption = models.FloatField(validators=[MinValueValidator(0)])
    transportation_distance = models.FloatField(validators=[MinValueValidator(0)])
    production_level = models.FloatField(validators=[MinValueValidator(0)])
    total_emission = models.FloatField(validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, default="Pending")  # Pending / Verified / Rejected
    recorded_date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_date"]

    def __str__(self):
        return f"{self.organization} - {self.recorded_date}"


class EmissionPrediction(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    electricity_consumption = models.FloatField(validators=[MinValueValidator(0)])
    fuel_consumption = models.FloatField(validators=[MinValueValidator(0)])
    transportation_distance = models.FloatField(validators=[MinValueValidator(0)])
    production_level = models.FloatField(validators=[MinValueValidator(0)])
    predicted_emission = models.FloatField(validators=[MinValueValidator(0)])
    prediction_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-prediction_date"]

    def __str__(self):
        return f"{self.organization} - {self.predicted_emission}"


class EmissionLimit(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    emission_limit = models.FloatField(validators=[MinValueValidator(0)])
    year = models.IntegerField()

    class Meta:
        ordering = ["-year"]
        unique_together = ("organization", "year")

    def __str__(self):
        return f"{self.organization} - {self.year}"


class CarbonCreditWallet(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE)
    available_credits = models.FloatField(default=0, validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization} - {self.available_credits}"


class CarbonCreditListing(models.Model):
    seller = models.ForeignKey(Organization, on_delete=models.CASCADE)
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    price_per_credit = models.FloatField(validators=[MinValueValidator(0)])
    status = models.CharField(max_length=30, default="Available")  # Available / Sold / Cancelled
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seller} - {self.quantity} credits"


class CarbonCreditTransaction(models.Model):
    buyer = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="purchases")
    seller = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sales")
    listing = models.ForeignKey(CarbonCreditListing, on_delete=models.PROTECT)
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    price_per_credit = models.FloatField(validators=[MinValueValidator(0)])
    total_price = models.FloatField(validators=[MinValueValidator(0)])
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="Completed")

    class Meta:
        ordering = ["-transaction_date"]

    def __str__(self):
        return f"{self.buyer} bought from {self.seller}"