# Library Service API

Library Service API is a backend solution for managing a library catalog and lending workflows. It provides a structured REST API built with Django REST Framework, featuring authentication, author and book management, borrowing operations, Stripe-based payments, Telegram notifications, and background task processing with Celery and Redis. The system also includes a custom Telegram bot that interacts with the API to provide real-time user notifications and commands.

## Project Demonstration
Detailed feature demonstration with screenshots is available in the pull request:
👉 https://github.com/illa-j/library-service/pull/1

## Features

- **User Management**: Custom user model using email as the unique identifier.
- **Authentication**: Secure authentication using JWT (JSON Web Tokens).
- **Google OAuth**:
   - Get Google authorization URL.
   - Authenticate using Google authorization code or Google ID token.
   - Automatic user creation/linking with JWT token issuance.
- **Authors & Books**:
  - CRUD for authors and books (admin-only for writes).
  - Image upload for author photos and book cover images.
- **Borrowing Workflow**:
  - List and retrieve borrowings.
  - Return borrowings (admin action) with automatic payment creation.
  - Overdue notifications (sent 1 day before due date via Celery).
- **Payments**:
  - List and retrieve payments.
  - Renew Stripe checkout session for pending/expired payments.
  - Stripe webhook integration for payment status updates.
- **Telegram Integration**:
  - Telegram webhook with basic commands.
  - Telegram linking token endpoint for account linking.
  - Telegram notifications about borrowing (overdue & creation) and successful payments.
- **API Documentation**: Interactive documentation using Swagger UI and ReDoc (drf-spectacular).
- **Throttling & Pagination**: Rate limiting and limit/offset pagination.
- **Background Tasks**: Celery worker + Celery beat for scheduled tasks.
- **Docker Support**: Containerized environment for development/deployment.

## Technologies Used

- **Framework**: [Django](https://www.djangoproject.com/) & [Django REST Framework](https://www.django-rest-framework.org/)
- **Database**: [PostgreSQL](https://www.postgresql.org/)
- **Authentication**: [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/)
- **Documentation**: [drf-spectacular](https://drf-spectacular.readthedocs.io/)
- **Task Queue**: [Celery](https://docs.celeryq.dev/) & [Redis](https://redis.io/)
- **Payments**: [Stripe](https://stripe.com/)
- **Containerization**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- **Config**: [python-dotenv](https://saurabh-kumar.com/python-dotenv/)
- **Formatting**: [Black](https://black.readthedocs.io/)

## Installation & Setup

### Using Docker (Recommended)

1. **Build and run the containers**:
   ```bash
   docker compose up --build
   ```

2. **The API will be available at**: `http://127.0.0.1:8000/`

### Local Development

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.sample .env
   ```
   Then populate it with your configuration (see [Environment Variables](#environment-variables)).

4. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Start the development server**:
   ```bash
   python manage.py runserver
   ```

## Environment Variables

Create a `.env` file in the project root. You can start from a sample file:

```bash
cp .env.sample .env
```

Then edit `.env` and set the values for your environment.

Example `.env`:

```env
SECRET_KEY=your_django_secret_key
ALLOWED_HOST=127.0.0.1
CSRF_TRUSTED_ORIGIN=http://127.0.0.1:8000

# Database Configuration
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Celery & Redis Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Email (SMTP)
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Stripe
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABCDEF...

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/users/google/login/
```

## .env.sample

This repository expects a `.env` file for configuration. Create a `.env.sample` file in the project root (or ask me to generate it) that includes the same keys as above with placeholder values. Then developers can run:

```bash
cp .env.sample .env
```

and fill in the secrets locally.

## API Documentation

Once the server is running:

- **OpenAPI Schema**: `http://127.0.0.1:8000/api/schema/`
- **Swagger UI**: `http://127.0.0.1:8000/api/schema/swagger-ui/`
- **ReDoc**: `http://127.0.0.1:8000/api/schema/redoc/`

## Authentication

This API uses JWT Authentication. To access protected endpoints:

1. **Register** at `POST /api/users/register/` (verification email is sent).
2. **Verify email** via `GET /api/users/verify-email/?token=<uuid>`.
3. **Obtain tokens** at `POST /api/users/token/`.
4. **Include the token** in the Authorization header of your requests:
   ```http
   Authorization: Bearer <your_access_token>
   ```

### Google OAuth Authentication

Google OAuth endpoints are available under `/api/users/`:

- `GET /api/users/google/url/` — returns `authorization_url` and `state`.
- `POST /api/users/google/` — exchanges Google authorization `code` for JWT tokens.
- `GET /api/users/google/login/?code=<code>&state=<state>` — callback endpoint for code exchange.
- `POST /api/users/google/token/` — authenticates with Google ID token (`token`) and returns JWT tokens.

Typical OAuth flow:

1. Call `GET /api/users/google/url/` and redirect user to `authorization_url`.
2. Google redirects to `GOOGLE_REDIRECT_URI` (`/api/users/google/login/`) with `code`.
3. API exchanges code, creates/links user, and returns JWT `access_token` + `refresh_token`.

## Base URLs & Endpoints

**API root**
- `/api/` is the API namespace.

**Users API** (`/api/users/`)
- Authentication and account management endpoints (register, JWT token operations, profile, logout, email verification, password change flows, Telegram linking token).

**Library API** (`/api/library/`)
- Core library resources (authors, books, borrowings, payments) exposed as REST endpoints.

**Schema & docs**
- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/schema/swagger-ui/`
- ReDoc: `/api/schema/redoc/`

**Webhooks**
- Stripe: `/stripe-webhook/` (Stripe events update payment status and can trigger notifications)
- Telegram: `/telegram-webhook/` (Telegram bot commands for linked users)
