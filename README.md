# InvoicePro

Phase 1 of the invoice management system is in place:

- Flask application factory
- SQLite database setup
- SQLAlchemy models for users and company settings
- Register, login, logout, and forgot-password UI
- Protected dashboard route
- CSRF protection and password hashing
- Basic test coverage for authentication and model wiring

## Local setup

1. Create a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and adjust values.
4. Initialize the database:
   `flask --app app init-db`
5. Run the server:
   `flask --app app run`

## Notes

- The forgot-password route is intentionally a UI placeholder in Phase 1.
- Phase 2 should build on the authenticated dashboard and expand the domain models.
