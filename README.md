# Carbon Credits Project

A Django-based web application for managing and tracking carbon emissions/credits.

## Project Structure

- **carbon/**: Django project configuration directory
  - `settings.py`: Django settings and configuration
  - `urls.py`: URL routing
  - `wsgi.py`: WSGI configuration for deployment
  - `asgi.py`: ASGI configuration for async deployment
  
- **myapp/**: Main Django application
  - `models.py`: Database models for carbon data
  - `views.py`: View functions for request handling
  - `admin.py`: Django admin configuration
  - `migrations/`: Database migration files

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv env
   ```

2. Activate the virtual environment:
   - Windows: `env\Scripts\activate`
   - Linux/Mac: `source env/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. Apply migrations:
   ```bash
   cd carbon
   python manage.py migrate
   ```

2. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

3. Run the development server:
   ```bash
   python manage.py runserver
   ```

The application will be available at `http://localhost:8000/`

## Admin Interface

Access the Django admin interface at `http://localhost:8000/admin/` with your superuser credentials.

## License

This project is part of the Carbon Credits initiative.
