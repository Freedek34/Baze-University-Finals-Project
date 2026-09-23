#!/bin/bash
# Simple database setup that creates user and database
# Run this to set up the database for CryptoVault

DB_NAME="cryptovault_db"
DB_USER="cryptovault_user"
DB_PASSWORD="cryptovault_pass"

echo "=== CryptoVault Database Setup ==="
echo ""
echo "This will create:"
echo "  - Database: $DB_NAME"
echo "  - User: $DB_USER"
echo "  - Password: $DB_PASSWORD"
echo ""

# Create user, database, and grant privileges using sudo -u postgres
echo "Step 1: Creating database and user..."
sudo -u postgres psql << EOF
-- Create user if not exists
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
  END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

if [ $? -ne 0 ]; then
    echo "Error creating database. Please make sure PostgreSQL is installed and you have sudo access."
    exit 1
fi

echo "✓ Database and user created"
echo ""

# Run schema files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
files=(
    "schema_postgres.sql"
    "schema_crypto.sql"
    "schema_deposit_features.sql"
    "schema_multi_wallets.sql"
)

for f in "${files[@]}"; do
    file_path="$SCRIPT_DIR/$f"
    if [ ! -f "$file_path" ]; then
        echo "Warning: File not found: $file_path"
        continue
    fi
    
    echo "Step 2: Running $f..."
    sudo -u postgres psql -d "$DB_NAME" -f "$file_path"
    
    if [ $? -ne 0 ]; then
        echo "Error running $f"
        exit 1
    fi
done

# Grant permissions on all tables to the user
echo ""
echo "Step 3: Granting table permissions..."
sudo -u postgres psql -d "$DB_NAME" << EOF
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

echo ""
echo "✓ Database setup complete!"
echo ""
echo "Database Configuration:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Password: $DB_PASSWORD"
echo ""
echo "Demo Login Credentials:"
echo "  Username: demo_user"
echo "  Email: demo@example.com"
echo "  Password: password123"
echo ""
echo "Add these to your .env file in Projectbackend/:"
echo "  DB_ENGINE=postgres"
echo "  DB_HOST=localhost"
echo "  DB_PORT=5432"
echo "  DB_NAME=$DB_NAME"
echo "  DB_USER=$DB_USER"
echo "  DB_PASSWORD=$DB_PASSWORD"
