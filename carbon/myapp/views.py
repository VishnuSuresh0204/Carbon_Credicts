from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.db.models import Sum, Avg, Count

from .models import (
    Login, Organization, EmissionRecord, EmissionPrediction,
    EmissionLimit, CarbonCreditWallet, CarbonCreditListing, CarbonCreditTransaction
)
from .services.emission_calculator import calculate_emission
from .ml_engine.predict import predict_emission_ml


def get_current_org(request):
    """Helper to safely retrieve the logged in organization, or None."""
    if not request.user.is_authenticated:
        return None
    return Organization.objects.filter(login=request.user).first()


def home(request):
    features = [
        {"icon": "⚡", "title": "Real-time Telemetry", "desc": "Live monitoring of industrial emissions with automated calculation engines."},
        {"icon": "🤖", "title": "AI Prediction Engine", "desc": "Neural-powered predictive modeling for carbon footprints and compliance forecasting."},
        {"icon": "💳", "title": "Credit Exchange", "desc": "Decentralized-style carbon credit marketplace for buying, selling, and offset trading."},
        {"icon": "🛡️", "title": "Verified ESG Ledger", "desc": "Authority-level verification, auditing trails, and automated regulatory compliance."},
    ]
    return render(request, "home.html", {"features": features})


def org_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    
    org = get_current_org(request)
    if not org:
        if request.user.usertype == "Admin":
            return redirect("/admin-home/")
        messages.error(request, "Organization profile not found.")
        return redirect("/login/")

    wallet, _ = CarbonCreditWallet.objects.get_or_create(organization=org)
    recent_records = EmissionRecord.objects.filter(organization=org).order_by("-recorded_date")[:5]
    total_emission_agg = EmissionRecord.objects.filter(organization=org).aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0
    verified_records_count = EmissionRecord.objects.filter(organization=org, status="Verified").count()
    active_listings_count = CarbonCreditListing.objects.filter(seller=org, status="Available").count()

    # Current year limit
    current_limit = EmissionLimit.objects.filter(organization=org).order_by("-year").first()

    context = {
        "org": org,
        "wallet": wallet,
        "recent_records": recent_records,
        "total_emission": round(total_emission_agg, 2),
        "verified_count": verified_records_count,
        "active_listings_count": active_listings_count,
        "current_limit": current_limit,
    }
    return render(request, "ORGANI/home.html", context)


def admin_home(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    if request.user.usertype != "Admin" and not request.user.is_superuser:
        messages.error(request, "Admin clearance required.")
        return redirect("/org-home/")

    organizations = Organization.objects.all().order_by("-created_at")
    pending_records = EmissionRecord.objects.filter(status="Pending").order_by("-recorded_date")
    all_records = EmissionRecord.objects.all()
    total_emission_sum = all_records.aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0
    total_credits_sum = CarbonCreditWallet.objects.aggregate(Sum("available_credits"))["available_credits__sum"] or 0.0
    total_transactions_sum = CarbonCreditTransaction.objects.aggregate(Sum("total_price"))["total_price__sum"] or 0.0

    context = {
        "organizations": organizations,
        "pending_records": pending_records,
        "total_emission_sum": round(total_emission_sum, 2),
        "total_credits_sum": round(total_credits_sum, 2),
        "total_transactions_sum": round(total_transactions_sum, 2),
        "total_orgs_count": organizations.count(),
        "pending_count": pending_records.count(),
    }
    return render(request, "ADMIN/home.html", context)


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        organization_name = request.POST.get("organization_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        industry_type = request.POST.get("industry_type", "").strip()

        if Login.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different handle.")
            return render(request, "register.html")

        user = Login.objects.create_user(
            username=username,
            password=password,
            usertype="Organization",
        )

        Organization.objects.create(
            login=user,
            organization_name=organization_name,
            email=email,
            phone=phone,
            address=address,
            industry_type=industry_type,
        )

        messages.success(request, "Organization registered successfully. Clearance granted &mdash; please log in.")
        return redirect("/login/")

    return render(request, "register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if user.usertype == "Admin" or user.is_superuser:
                return redirect("/admin-home/")
            return redirect("/org-home/")

        messages.error(request, "Invalid username or password credentials.")
        return render(request, "login.html")

    return render(request, "login.html")


def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have been securely disconnected.")
    return redirect("/login/")


# ---------------------------------------------------------------------
# ORGANIZATION PROFILE
# ---------------------------------------------------------------------

def profile(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        org.organization_name = request.POST.get("organization_name", org.organization_name)
        org.email = request.POST.get("email", org.email)
        org.phone = request.POST.get("phone", org.phone)
        org.address = request.POST.get("address", org.address)
        org.industry_type = request.POST.get("industry_type", org.industry_type)
        org.save()
        messages.success(request, "Organization profile telemetry successfully updated.")
        return redirect("/profile/")

    wallet, _ = CarbonCreditWallet.objects.get_or_create(organization=org)
    total_records = EmissionRecord.objects.filter(organization=org).count()
    return render(request, "ORGANI/profile.html", {"org": org, "wallet": wallet, "total_records": total_records})


# ---------------------------------------------------------------------
# EMISSION MODULE
# ---------------------------------------------------------------------

def add_emission(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        try:
            electricity = float(request.POST.get("electricity_consumption", 0))
            fuel = float(request.POST.get("fuel_consumption", 0))
            distance = float(request.POST.get("transportation_distance", 0))
            production = float(request.POST.get("production_level", 0))
        except ValueError:
            messages.error(request, "Please provide valid numeric inputs.")
            return render(request, "ORGANI/add_emission.html", {"org": org})

        total = calculate_emission(electricity, fuel, distance, production)

        record = EmissionRecord.objects.create(
            organization=org,
            electricity_consumption=electricity,
            fuel_consumption=fuel,
            transportation_distance=distance,
            production_level=production,
            total_emission=total,
        )

        messages.success(request, f"Emission log #{record.id} calculated ({total} tCO2) and submitted for admin verification.")
        return redirect("/emission-history/")

    return render(request, "ORGANI/add_emission.html", {"org": org})


def emission_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    records = EmissionRecord.objects.filter(organization=org).order_by("-recorded_date")
    total_emission = records.aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0
    verified_count = records.filter(status="Verified").count()
    pending_count = records.filter(status="Pending").count()

    context = {
        "org": org,
        "records": records,
        "total_emission": round(total_emission, 2),
        "verified_count": verified_count,
        "pending_count": pending_count,
    }
    return render(request, "ORGANI/emission_history.html", context)


# ---------------------------------------------------------------------
# ML PREDICTION MODULE
# ---------------------------------------------------------------------

def predict(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    predicted = None
    input_data = {}

    if request.method == "POST":
        try:
            electricity = float(request.POST.get("electricity_consumption", 0))
            fuel = float(request.POST.get("fuel_consumption", 0))
            distance = float(request.POST.get("transportation_distance", 0))
            production = float(request.POST.get("production_level", 0))

            input_data = {
                "electricity": electricity,
                "fuel": fuel,
                "distance": distance,
                "production": production,
            }

            predicted = predict_emission_ml(electricity, fuel, distance, production)

            EmissionPrediction.objects.create(
                organization=org,
                electricity_consumption=electricity,
                fuel_consumption=fuel,
                transportation_distance=distance,
                production_level=production,
                predicted_emission=predicted,
            )
            messages.success(request, f"Neural network prediction generated: {predicted} tCO2 estimated.")
        except ValueError:
            messages.error(request, "Invalid parameter values for AI prediction.")

    recent_predictions = EmissionPrediction.objects.filter(organization=org).order_by("-prediction_date")[:5]

    context = {
        "org": org,
        "predicted": predicted,
        "input_data": input_data,
        "recent_predictions": recent_predictions,
    }
    return render(request, "ORGANI/predict.html", context)


# ---------------------------------------------------------------------
# CARBON CREDIT WALLET
# ---------------------------------------------------------------------

def wallet(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    wallet_obj, _ = CarbonCreditWallet.objects.get_or_create(organization=org)
    my_listings = CarbonCreditListing.objects.filter(seller=org).order_by("-created_at")
    recent_purchases = CarbonCreditTransaction.objects.filter(buyer=org).order_by("-transaction_date")[:5]
    recent_sales = CarbonCreditTransaction.objects.filter(seller=org).order_by("-transaction_date")[:5]

    context = {
        "org": org,
        "wallet": wallet_obj,
        "my_listings": my_listings,
        "recent_purchases": recent_purchases,
        "recent_sales": recent_sales,
    }
    return render(request, "ORGANI/wallet.html", context)


# ---------------------------------------------------------------------
# MARKETPLACE / TRADING
# ---------------------------------------------------------------------

def create_listing(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    wallet_obj, _ = CarbonCreditWallet.objects.get_or_create(organization=org)

    if request.method == "POST":
        try:
            quantity = float(request.POST.get("quantity", 0))
            price = float(request.POST.get("price_per_credit", 0))
        except ValueError:
            messages.error(request, "Invalid numeric values entered.")
            return redirect("/create-listing/")

        if quantity <= 0 or price <= 0:
            messages.error(request, "Quantity and price must be greater than zero.")
            return redirect("/create-listing/")

        if quantity > wallet_obj.available_credits:
            messages.error(request, f"Insufficient balance. You have {wallet_obj.available_credits} credits available.")
            return redirect("/create-listing/")

        CarbonCreditListing.objects.create(
            seller=org,
            quantity=quantity,
            price_per_credit=price,
        )

        wallet_obj.available_credits -= quantity
        wallet_obj.save()

        messages.success(request, f"Order created: {quantity} Carbon Credits listed at ${price}/credit.")
        return redirect("/marketplace/")

    return render(request, "ORGANI/create_listing.html", {"org": org, "wallet": wallet_obj})


def marketplace(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)

    listings = CarbonCreditListing.objects.filter(status="Available").exclude(
        seller__login=request.user
    ).order_by("-created_at")

    my_listings = CarbonCreditListing.objects.filter(seller=org).order_by("-created_at") if org else []
    wallet_obj, _ = CarbonCreditWallet.objects.get_or_create(organization=org) if org else (None, False)

    context = {
        "org": org,
        "listings": listings,
        "my_listings": my_listings,
        "wallet": wallet_obj,
    }
    return render(request, "ORGANI/marketplace.html", context)


def buy_credit(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    if request.method == "POST":
        listing_id = request.POST.get("listing_id")
        try:
            quantity = float(request.POST.get("quantity", 0))
        except ValueError:
            messages.error(request, "Please enter a valid quantity.")
            return redirect("/marketplace/")

        listing = get_object_or_404(CarbonCreditListing, id=listing_id, status="Available")

        if listing.seller == org:
            messages.error(request, "You cannot purchase your own credit listing.")
            return redirect("/marketplace/")

        if quantity <= 0:
            messages.error(request, "Quantity must be greater than 0.")
            return redirect("/marketplace/")

        if quantity > listing.quantity:
            messages.error(request, f"Requested quantity ({quantity}) exceeds available listing amount ({listing.quantity}).")
            return redirect("/marketplace/")

        total_price = round(quantity * listing.price_per_credit, 2)

        CarbonCreditTransaction.objects.create(
            buyer=org,
            seller=listing.seller,
            listing=listing,
            quantity=quantity,
            price_per_credit=listing.price_per_credit,
            total_price=total_price,
        )

        buyer_wallet, _ = CarbonCreditWallet.objects.get_or_create(organization=org)
        buyer_wallet.available_credits += quantity
        buyer_wallet.save()

        # Update seller wallet revenue/credits if needed, or seller already held credits
        listing.quantity -= quantity
        if listing.quantity <= 0.0001:
            listing.status = "Sold"
            listing.quantity = 0
        listing.save()

        messages.success(request, f"Trade completed! Successfully purchased {quantity} Carbon Credits for ${total_price}.")
        return redirect("/wallet/")

    return redirect("/marketplace/")


def transaction_history(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    org = get_current_org(request)
    if not org:
        return redirect("/login/")

    purchases = CarbonCreditTransaction.objects.filter(buyer=org).order_by("-transaction_date")
    sales = CarbonCreditTransaction.objects.filter(seller=org).order_by("-transaction_date")

    total_bought_credits = purchases.aggregate(Sum("quantity"))["quantity__sum"] or 0.0
    total_spent = purchases.aggregate(Sum("total_price"))["total_price__sum"] or 0.0
    total_sold_credits = sales.aggregate(Sum("quantity"))["quantity__sum"] or 0.0
    total_earned = sales.aggregate(Sum("total_price"))["total_price__sum"] or 0.0

    context = {
        "org": org,
        "purchases": purchases,
        "sales": sales,
        "total_bought_credits": round(total_bought_credits, 2),
        "total_spent": round(total_spent, 2),
        "total_sold_credits": round(total_sold_credits, 2),
        "total_earned": round(total_earned, 2),
    }
    return render(request, "ORGANI/transaction_history.html", context)


# ---------------------------------------------------------------------
# ADMIN MODULE
# ---------------------------------------------------------------------

def verify_emission(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    if request.method == "POST":
        record_id = request.POST.get("record_id")
        action = request.POST.get("action")  # "verify" or "reject"

        record = get_object_or_404(EmissionRecord, id=record_id)
        record.status = "Verified" if action == "verify" else "Rejected"
        record.save()

        if record.status == "Verified":
            _update_wallet_after_verification(record)

        messages.success(request, f"Emission record #{record.id} for '{record.organization.organization_name}' has been marked as {record.status}.")
        return redirect(request.META.get('HTTP_REFERER', '/admin-home/'))

    return redirect("/admin-home/")


def set_emission_limit(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        messages.error(request, "Admin access required.")
        return redirect("/login/")

    if request.method == "POST":
        org_id = request.POST.get("org_id")
        try:
            year = int(request.POST.get("year", 2026))
            limit_value = float(request.POST.get("emission_limit", 0))
        except ValueError:
            messages.error(request, "Please enter valid numeric values for year and emission limit.")
            return redirect("/admin-home/")

        org = get_object_or_404(Organization, id=org_id)

        limit_obj, created = EmissionLimit.objects.get_or_create(
            organization=org, year=year, defaults={"emission_limit": limit_value}
        )
        if not created:
            limit_obj.emission_limit = limit_value
            limit_obj.save()

        messages.success(request, f"Emission ceiling of {limit_value} tCO2 for Year {year} configured for '{org.organization_name}'.")
        return redirect(request.META.get('HTTP_REFERER', '/admin-home/'))

    return redirect("/admin-home/")


def admin_organizations(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        return redirect("/login/")

    organizations = Organization.objects.all().order_by("-created_at")
    org_data = []
    for org in organizations:
        rec_count = EmissionRecord.objects.filter(organization=org).count()
        tot_emission = EmissionRecord.objects.filter(organization=org).aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0
        wallet_obj = CarbonCreditWallet.objects.filter(organization=org).first()
        limit_obj = EmissionLimit.objects.filter(organization=org).order_by("-year").first()
        org_data.append({
            "org": org,
            "records_count": rec_count,
            "total_emission": round(tot_emission, 2),
            "credits": wallet_obj.available_credits if wallet_obj else 0.0,
            "limit": limit_obj.emission_limit if limit_obj else None,
            "limit_year": limit_obj.year if limit_obj else None,
        })

    return render(request, "ADMIN/organizations.html", {"org_data": org_data, "total_count": organizations.count()})


def admin_emissions(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        return redirect("/login/")

    records = EmissionRecord.objects.all().select_related("organization").order_by("-recorded_date")
    organizations = Organization.objects.all()
    pending_records = records.filter(status="Pending")
    verified_records = records.filter(status="Verified")
    rejected_records = records.filter(status="Rejected")

    context = {
        "records": records,
        "organizations": organizations,
        "pending_records": pending_records,
        "verified_records": verified_records,
        "rejected_records": rejected_records,
        "total_emissions": round(records.aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0, 2),
    }
    return render(request, "ADMIN/emissions.html", context)


def admin_credits(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        return redirect("/login/")

    wallets = CarbonCreditWallet.objects.all().select_related("organization")
    listings = CarbonCreditListing.objects.all().select_related("seller").order_by("-created_at")
    transactions = CarbonCreditTransaction.objects.all().select_related("buyer", "seller", "listing").order_by("-transaction_date")

    total_credits = wallets.aggregate(Sum("available_credits"))["available_credits__sum"] or 0.0
    total_volume = transactions.aggregate(Sum("total_price"))["total_price__sum"] or 0.0

    context = {
        "wallets": wallets,
        "listings": listings,
        "transactions": transactions,
        "total_credits": round(total_credits, 2),
        "total_volume": round(total_volume, 2),
    }
    return render(request, "ADMIN/credits.html", context)


def admin_reports(request):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        return redirect("/login/")

    total_orgs = Organization.objects.count()
    all_emissions = EmissionRecord.objects.all()
    total_co2 = all_emissions.aggregate(Sum("total_emission"))["total_emission__sum"] or 0.0
    avg_emission = all_emissions.aggregate(Avg("total_emission"))["total_emission__avg"] or 0.0
    verified_count = all_emissions.filter(status="Verified").count()
    pending_count = all_emissions.filter(status="Pending").count()

    # Sector breakdown
    industry_stats = (
        Organization.objects.values("industry_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "total_orgs": total_orgs,
        "total_co2": round(total_co2, 2),
        "avg_emission": round(avg_emission, 2),
        "verified_count": verified_count,
        "pending_count": pending_count,
        "industry_stats": industry_stats,
    }
    return render(request, "ADMIN/reports.html", context)


def admin_delete_org(request, org_id):
    if not request.user.is_authenticated or (request.user.usertype != "Admin" and not request.user.is_superuser):
        return redirect("/login/")

    org = get_object_or_404(Organization, id=org_id)
    org_name = org.organization_name
    login_user = org.login
    org.delete()
    if login_user:
        login_user.delete()

    messages.success(request, f"Organization '{org_name}' and associated credentials deleted.")
    return redirect("/admin-organizations/")


def _update_wallet_after_verification(record):
    org = record.organization
    limit_obj = EmissionLimit.objects.filter(
        organization=org, year=record.recorded_date.year
    ).first()

    if not limit_obj:
        return

    surplus = limit_obj.emission_limit - record.total_emission
    if surplus > 0:
        wallet_obj, _ = CarbonCreditWallet.objects.get_or_create(organization=org)
        wallet_obj.available_credits += surplus
        wallet_obj.save()