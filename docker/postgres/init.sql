-- Create test database for testing isolation
CREATE DATABASE validahub_test;

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions to validahub user
GRANT ALL PRIVILEGES ON DATABASE validahub TO validahub;
GRANT ALL PRIVILEGES ON DATABASE validahub_test TO validahub;