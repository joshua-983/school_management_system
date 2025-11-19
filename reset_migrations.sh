#!/bin/bash
echo "🧹 Resetting migrations and database..."

# Stop containers
echo "Stopping containers..."
docker-compose down

# Remove volumes (WARNING: This will delete your data)
echo "Removing volumes..."
docker-compose down -v

# Remove migration files but keep __init__.py
echo "Cleaning migration files..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# Clean pycache
echo "Cleaning pycache..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete

echo "Rebuilding containers..."
docker-compose build --no-cache

echo "Starting services..."
docker-compose up -d

echo "Waiting for services to be ready..."
sleep 30

# Check if services are healthy
echo "Checking service health..."
docker-compose ps

# Create new migrations
echo "Creating new migrations..."
docker-compose exec web python manage.py makemigrations

# Apply migrations
echo "Applying migrations..."
docker-compose exec web python manage.py migrate

# Create superuser (optional)
echo "Would you like to create a superuser? (y/n)"
read create_su
if [ "$create_su" = "y" ] || [ "$create_su" = "Y" ]; then
    docker-compose exec web python manage.py createsuperuser
fi

echo "✅ Reset complete!"
echo "🎉 Your application should be running at http://localhost:8000"
