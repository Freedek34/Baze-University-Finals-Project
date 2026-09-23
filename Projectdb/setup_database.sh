#!/bin/bash
# CryptoVault - Run all PostgreSQL schema files in order (Linux/Mac version)
# Usage: cd Projectdb; ./setup_database.sh

DB_NAME="cryptovault_db"
DB_USER="${DB_USER:-postgres}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting up PostgreSQL database: $DB_NAME"
echo "Using database user: $DB_USER"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "Error: psql not found. Please install PostgreSQL client."
    exit 1
fi

# Create database if it doesn't exist
echo "Creating database if needed..."
psql -U "$DB_USER" -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create database. Make sure PostgreSQL is running and you have the correct permissions."
    echo "You may need to run: sudo -u postgres psql -c \"CREATE DATABASE $DB_NAME\""
    exit 1
fi

# Run schema files in order
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
    
    echo ""
    echo "=== Running $f ==="
    psql -U "$DB_USER" -d "$DB_NAME" -f "$file_path"
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed running $f"
        exit 1
    fi
done

echo ""
echo "✓ Database setup complete: $DB_NAME"
echo ""
echo "Demo credentials:"
echo "  Username: demo_user"
echo "  Password: password123"
