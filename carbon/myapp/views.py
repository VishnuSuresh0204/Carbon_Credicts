from django.http import request
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import *
from .services.emission_calculator import calculate_emission
from .ml_engine.predict import predict_emission_ml


def home(request):
    return render(request, "home.html")


def org_home(request):
    org = Organization.objects.get(login=request.user)
    wallet, created = CarbonCreditWallet.objects.get_or_create(organization=org)
    recent_records = EmissionRecord.objects.filter(organization=org)[:5]

    context = {
        "org": org,
        "wallet": wallet,
        "recent_records": recent_records,
    }
    return render(request, "ORGANI/home.html", context)


def admin_home(request):
    organizations = Organization.objects.all()
    pending_records = EmissionRecord.objects.filter(status="Pending")

    context = {
        "organizations": organizations,
        "pending_records": pending_records,
    }
    return render(request, "ADMIN/home.html", context)


def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        organization_name = request.POST.get("organization_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        industry_type = request.POST.get("industry_type")

        if Login.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return render(request, "register.html")

        user = Login.objects.create_user(
            username=username,
            password=password,
            usertype="Organization",
        )

        org = Organization.objects.create(
            login=user,
            organization_name=organization_name,
            email=email,
            phone=phone,
            address=address,
            industry_type=industry_type,
        )

        messages.success(request, "Registration successful. Please login.")
        return redirect("/login/")

    return render(request, "register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            if user.usertype == "Admin":
                return redirect("/admin-home/")
            return redirect("/org-home/")

        messages.error(request, "Invalid credentials")
        return render(request, "login.html")

    return render(request, "login.html")


def logout_view(request):
    auth_logout(request)
    return redirect("/login/")


# ---------------------------------------------------------------------
# ORGANIZATION PROFILE
# ---------------------------------------------------------------------

def profile(request):
    org = Organization.objects.get(login=request.user)

    if request.method == "POST":
        org.organization_name = request.POST.get("organization_name")
        org.email = request.POST.get("email")
        org.phone = request.POST.get("phone")
        org.address = request.POST.get("address")
        org.industry_type = request.POST.get("industry_type")
        org.save()
        messages.success(request, "Profile updated")
        return redirect("/profile/")

    return render(request, "ORGANI/profile.html", {"org": org})


# ---------------------------------------------------------------------
# EMISSION MODULE
# ---------------------------------------------------------------------

def add_emission(request):
    org = Organization.objects.get(login=request.user)

    if request.method == "POST":
        electricity = float(request.POST.get("electricity_consumption"))
        fuel = float(request.POST.get("fuel_consumption"))
        distance = float(request.POST.get("transportation_distance"))
        production = float(request.POST.get("production_level"))

        total = calculate_emission(electricity, fuel, distance, production)

        EmissionRecord.objects.create(
            organization=org,
            electricity_consumption=electricity,
            fuel_consumption=fuel,
            transportation_distance=distance,
            production_level=production,
            total_emission=total,
        )

        messages.success(request, "Emission record saved")
        return redirect("/emission-history/")

    return render(request, "ORGANI/add_emission.html")


def emission_history(request):
    org = Organization.objects.get(login=request.user)
    records = EmissionRecord.objects.filter(organization=org)
    return render(request, "ORGANI/emission_history.html", {"records": records})


# ---------------------------------------------------------------------
# ML PREDICTION MODULE
# ---------------------------------------------------------------------

def predict(request):
    org = Organization.objects.get(login=request.user)
    predicted = None

    if request.method == "POST":
        electricity = float(request.POST.get("electricity_consumption"))
        fuel = float(request.POST.get("fuel_consumption"))
        distance = float(request.POST.get("transportation_distance"))
        production = float(request.POST.get("production_level"))

        predicted = predict_emission_ml(electricity, fuel, distance, production)

        EmissionPrediction.objects.create(
            organization=org,
            electricity_consumption=electricity,
            fuel_consumption=fuel,
            transportation_distance=distance,
            production_level=production,
            predicted_emission=predicted,
        )

    return render(request, "ORGANI/predict.html", {"predicted": predicted})


# ---------------------------------------------------------------------
# CARBON CREDIT WALLET
# ---------------------------------------------------------------------

def wallet(request):
    org = Organization.objects.get(login=request.user)
    wallet_obj, created = CarbonCreditWallet.objects.get_or_create(organization=org)
    return render(request, "ORGANI/wallet.html", {"wallet": wallet_obj})


# ---------------------------------------------------------------------
# MARKETPLACE / TRADING
# ---------------------------------------------------------------------

def create_listing(request):
    org = Organization.objects.get(login=request.user)
    wallet_obj, created = CarbonCreditWallet.objects.get_or_create(organization=org)

    if request.method == "POST":
        quantity = float(request.POST.get("quantity"))
        price = float(request.POST.get("price_per_credit"))

        if quantity > wallet_obj.available_credits:
            messages.error(request, "Not enough credits to list")
            return redirect("/create-listing/")

        CarbonCreditListing.objects.create(
            seller=org,
            quantity=quantity,
            price_per_credit=price,
        )

        wallet_obj.available_credits -= quantity
        wallet_obj.save()

        messages.success(request, "Listing created")
        return redirect("/marketplace/")

    return render(request, "ORGANI/create_listing.html")


def marketplace(request):
    listings = CarbonCreditListing.objects.filter(status="Available").exclude(
        seller__login=request.user
    )
    return render(request, "ORGANI/marketplace.html", {"listings": listings})


def buy_credit(request):
    """Listing id is submitted as a hidden field in the marketplace form, not via the URL."""
    org = Organization.objects.get(login=request.user)

    if request.method == "POST":
        listing_id = request.POST.get("listing_id")
        quantity = float(request.POST.get("quantity"))

        listing = CarbonCreditListing.objects.get(id=listing_id, status="Available")

        if quantity > listing.quantity:
            messages.error(request, "Requested quantity exceeds listing")
            return redirect("/marketplace/")

        total_price = quantity * listing.price_per_credit

        CarbonCreditTransaction.objects.create(
            buyer=org,
            seller=listing.seller,
            listing=listing,
            quantity=quantity,
            price_per_credit=listing.price_per_credit,
            total_price=total_price,
        )

        buyer_wallet, created = CarbonCreditWallet.objects.get_or_create(organization=org)
        buyer_wallet.available_credits += quantity
        buyer_wallet.save()

        listing.quantity -= quantity
        if listing.quantity <= 0:
            listing.status = "Sold"
        listing.save()

        messages.success(request, "Purchase successful")
        return redirect("/wallet/")

    return redirect("/marketplace/")


def transaction_history(request):
    org = Organization.objects.get(login=request.user)
    purchases = CarbonCreditTransaction.objects.filter(buyer=org)
    sales = CarbonCreditTransaction.objects.filter(seller=org)
    return render(
        request,
        "ORGANI/transaction_history.html",
        {"purchases": purchases, "sales": sales},
    )


# ---------------------------------------------------------------------
# ADMIN MODULE
# ---------------------------------------------------------------------

def verify_emission(request):
    """Emission record id comes from a hidden field in the admin template."""
    if request.method == "POST":
        record_id = request.POST.get("record_id")
        action = request.POST.get("action")  # "verify" or "reject"

        record = EmissionRecord.objects.get(id=record_id)
        record.status = "Verified" if action == "verify" else "Rejected"
        record.save()

        if record.status == "Verified":
            _update_wallet_after_verification(record)

        messages.success(request, f"Record {record.status.lower()}")
        return redirect("/admin-home/")

    return redirect("/admin-home/")


def set_emission_limit(request):
    """Organization id comes from a hidden field in the admin template."""
    if request.method == "POST":
        org_id = request.POST.get("org_id")
        year = int(request.POST.get("year"))
        limit_value = float(request.POST.get("emission_limit"))

        org = Organization.objects.get(id=org_id)

        limit_obj, created = EmissionLimit.objects.get_or_create(
            organization=org, year=year, defaults={"emission_limit": limit_value}
        )
        if not created:
            limit_obj.emission_limit = limit_value
            limit_obj.save()

        messages.success(request, "Emission limit set")
        return redirect("/admin-home/")

    return redirect("/admin-home/")


def _update_wallet_after_verification(record):
    org = record.organization
    limit_obj = EmissionLimit.objects.filter(
        organization=org, year=record.recorded_date.year
    ).first()

    if not limit_obj:
        return

    surplus = limit_obj.emission_limit - record.total_emission
    if surplus > 0:
        wallet_obj, created = CarbonCreditWallet.objects.get_or_create(organization=org)
        wallet_obj.available_credits += surplus
        wallet_obj.save()