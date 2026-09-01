from django.http import request
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
 
from .models import *
 

def home(request):
    return render(request, "home.html")

def org_home(request):
    
    return render(request, "ORGANI/home.html")

def admin_home(request):
    return render(request, "ADMIN/home.html")

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



 
 