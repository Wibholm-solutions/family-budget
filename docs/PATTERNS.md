# Family Budget - Coding Patterns

Centralized coding standards and patterns for AI agent development.

## Table of Contents

1. [Frontend Patterns](#frontend-patterns)
   - [Modal Pattern](#modal-pattern)
   - [Form Input Pattern](#form-input-pattern)
   - [Select Dropdown Pattern](#select-dropdown-pattern)
   - [Button Pattern](#button-pattern)
2. [Backend Patterns](#backend-patterns)
   - [FastAPI Route Pattern](#fastapi-route-pattern)
   - [Form Endpoint Pattern](#form-endpoint-pattern)
   - [Authentication Check Pattern](#authentication-check-pattern)
   - [Danish Amount Parsing](#danish-amount-parsing)
3. [Security Patterns](#security-patterns)
   - [Password Hashing](#password-hashing)
   - [Session Management](#session-management)
   - [Input Validation](#input-validation)
4. [Database Patterns](#database-patterns)
   - [CRUD Operations](#crud-operations)
   - [User Isolation](#user-isolation)
5. [Testing Patterns](#testing-patterns)
   - [Route Testing](#route-testing)
   - [Database Testing](#database-testing)
   - [E2E Testing](#e2e-testing)

---

## Frontend Patterns

### Modal Pattern

**When to use**: Any popup form or dialog (expense add/edit, category edit, feedback, etc.)

**Reference**: Search for `id="modal"` in `templates/expenses.html`

```html
<!-- Modal Container -->
<div id="modal" class="fixed inset-0 bg-black/50 flex items-end justify-center z-50 hidden">
    <div class="bg-white dark:bg-gray-800 w-full max-w-md rounded-t-2xl p-6 animate-slide-up">
        <div class="flex justify-between items-center mb-4">
            <h2 id="modal-title" class="text-xl font-bold text-gray-900 dark:text-white">Title</h2>
            <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <i data-lucide="x" class="w-6 h-6"></i>
            </button>
        </div>
        <form id="form-id" method="post" action="/budget/endpoint" class="space-y-4">
            <!-- Form fields -->
        </form>
    </div>
</div>
```

**Key points**:
- Use `fixed inset-0 bg-black/50` for backdrop
- Use `items-end justify-center` for bottom slide-up animation
- Use `animate-slide-up` CSS class (defined in `base.html`)
- Use `hidden` class to toggle visibility
- Include backdrop click handler to close
- Include Escape key handler to close
- Always include dark mode variants

**JavaScript pattern** (in template `<script>` tag):

```javascript
function openModal() {
    document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

// Close on backdrop click
document.getElementById('modal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Close on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});
```

**Examples in codebase**:
- Add/edit expense modals: `templates/expenses.html`
- Add/edit category modals: `templates/categories.html`

---

### Form Input Pattern

**When to use**: All text input fields

**Reference**: See form fields in `templates/expenses.html` and `templates/categories.html`

```html
<div>
    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Label Text
    </label>
    <input
        type="text"
        name="field-name"
        id="field-id"
        placeholder="f.eks. eksempel"
        class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
        required
    >
</div>
```

**Key points**:
- Always use `rounded-xl` for border radius
- Always use `px-4 py-3` for padding
- Always include dark mode variants (`dark:bg-gray-700`, etc.)
- Use `focus:ring-2 focus:ring-primary` for focus states
- Use `outline-none` to hide default outline (ring replaces it)
- Label above input with `mb-1` spacing
- Use semantic `id` attributes for accessibility

**Textarea variant**:

```html
<textarea
    name="message"
    rows="5"
    class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
    required
></textarea>
```

---

### Select Dropdown Pattern

**When to use**: Dropdowns, category selection, frequency selection

```html
<div>
    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        Label Text
    </label>
    <select
        name="field-name"
        id="field-id"
        class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
        required
    >
        <option value="value1">Option 1</option>
    </select>
</div>
```

**Frequency dropdown** (used in expenses and income):

```html
<select name="frequency" class="...">
    <option value="monthly">Månedlig</option>
    <option value="quarterly">Kvartalsvis</option>
    <option value="semi-annual">Halvårlig</option>
    <option value="yearly">Årlig</option>
</select>
```

**Category dropdown from database**:

```html
<select name="category" class="...">
    {% for cat in categories %}
    <option value="{{ cat.name }}">{{ cat.name }}</option>
    {% endfor %}
</select>
```

---

### Button Pattern

**Primary action button**:

```html
<button
    type="submit"
    class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-xl transition-colors"
>
    Button Text
</button>
```

**Secondary/cancel button**:

```html
<button
    type="button"
    onclick="closeModal()"
    class="w-full bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-white font-medium py-3 px-4 rounded-xl transition-colors"
>
    Annuller
</button>
```

**Icon button (small)**:

```html
<button class="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1">
    <i data-lucide="pencil" class="w-3 h-3"></i>
    Rediger
</button>
```

**Destructive action (delete)**:

```html
<button class="text-red-500 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 flex items-center gap-1">
    <i data-lucide="trash-2" class="w-3 h-3"></i>
    Slet
</button>
```

**Key points**:
- Use `transition-colors` for smooth hover effects
- Always include dark mode variants
- Use Lucide icons for visual cues
- Use semantic colors (red for delete, etc.)

---

## Backend Patterns

### FastAPI Route Pattern

**GET route (page display)**:

```python
@app.get("/budget/[route]", response_class=HTMLResponse)
async def route_name(request: Request):
    """One-line description of what this route does."""
    # Check authentication if required
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse("/budget/login", status_code=303)

    # Get data from database
    data = db.get_something(user_id)

    # Render template
    return templates.TemplateResponse("template.html", {
        "request": request,
        "data": data,
    })
```

**POST route (form handling)**:

```python
@app.post("/budget/[route]")
async def route_action(
    request: Request,
    field1: str = Form(...),
    field2: str = Form(...),
):
    """Process form submission."""
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse("/budget/login", status_code=303)

    try:
        db.do_something(user_id, field1, field2)
        return RedirectResponse("/budget/route", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("template.html", {
            "request": request,
            "error": "Fejl besked"
        })
```

**Key points**:
- Use `async def` for all routes
- Use `Form(...)` for required form fields
- Use `status_code=303` for POST-redirect-GET pattern
- Always check authentication first
- Return `RedirectResponse` for POST success

**Reference**: See `async def login` and `async def login_page` in `src/api.py`

---

### Form Endpoint Pattern

**Multiple form inputs (dynamic keys)** - used for income management:

```python
@app.post("/budget/income")
async def update_income(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse("/budget/login", status_code=303)

    form = await request.form()
    db.delete_all_income(user_id)

    i = 0
    while True:
        person = form.get(f'person_{i}')
        amount = form.get(f'amount_{i}')
        frequency = form.get(f'frequency_{i}')

        if not person:
            break

        if person.strip() and amount:
            parsed_amount = parse_danish_amount(amount)
            db.add_income(user_id, person, parsed_amount, frequency)

        i += 1

    return RedirectResponse("/budget/income", status_code=303)
```

**Key points**:
- Use `await request.form()` for dynamic fields
- Use numbered suffixes (`field_0`, `field_1`, etc.)
- Break loop when field is missing
- Validate each entry before processing

**Reference**: See `async def update_income` in `src/api.py`

---

### Authentication Check Pattern

**Standard auth check**:

```python
user_id = get_user_id(request)
if user_id is None:
    return RedirectResponse("/budget/login", status_code=303)
```

**Optional auth (different content if logged in)**:

```python
user_id = get_user_id(request)
# Don't redirect - just pass user_id (may be None)
return templates.TemplateResponse("template.html", {
    "request": request,
    "user_id": user_id,
})
```

**Reference**: See `def get_user_id` and `def is_demo_mode` in `src/api.py`

---

### Danish Amount Parsing

**When to use**: All amount inputs from forms

```python
# In route handler
amount_str = form_data.get('amount')  # e.g., "25.000,50"
amount_float = parse_danish_amount(amount_str)  # -> 25000.50
```

**Key points**:
- Accepts both formats: "25.000,50" (Danish) and "25000.50" (standard)
- Removes thousand separators (periods in Danish format)
- Converts comma decimal to period
- Returns float for database storage

**Display pattern** (in templates):

```python
# format_currency in api.py formats amount as Danish currency
# Used in templates: {{ format_currency(expense.amount) }}
# Output: "25.000,50 kr."
```

**Reference**: See `def parse_danish_amount` and `def format_currency` in `src/api.py`

---

## Security Patterns

### Password Hashing

**NEVER store plain passwords. Always use PBKDF2 hashing.**

```python
from src.database import hash_password, verify_password

# Hash new password (registration, password reset)
password_hash, salt = hash_password(plain_password)

# Verify password (login)
is_valid = verify_password(plain_password, stored_hash, stored_salt)
```

**Key points**:
- Uses PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP 2023 standard)
- Generates random 32-byte salt per password
- Uses constant-time comparison (`secrets.compare_digest`)
- Stores hash and salt as hex strings
- Why not bcrypt: stdlib dependency avoids C extensions, simpler deployment

**Reference**: See `def hash_password` and `def verify_password` in `src/database.py`

---

### Session Management

```python
import secrets
import hashlib

# Create session (login)
session_id = secrets.token_urlsafe(32)
SESSIONS[hash_token(session_id)] = user_id
save_sessions(SESSIONS)

# Set cookie
response.set_cookie(
    key="budget_session",
    value=session_id,
    httponly=True,      # Prevent JavaScript access
    secure=True,        # HTTPS only
    samesite="lax",     # CSRF protection
    max_age=86400 * 30  # 30 days
)

# Verify session (every request)
session_id = request.cookies.get("budget_session")
if session_id:
    user_id = SESSIONS.get(hash_token(session_id))

# Destroy session (logout)
session_id = request.cookies.get("budget_session")
if session_id:
    hashed = hash_token(session_id)
    if hashed in SESSIONS:
        del SESSIONS[hashed]
        save_sessions(SESSIONS)
```

**Key points**:
- Never store plain tokens - always hash with SHA-256
- Use `secrets.token_urlsafe()` for cryptographically secure tokens
- Set `httponly=True` to prevent XSS attacks
- Set `secure=True` for HTTPS-only transmission
- Set `samesite="lax"` for CSRF protection
- Sessions stored in `data/sessions.json` (file-based, sufficient for <100 users)
- Why not JWT: SSR app doesn't need stateless tokens, sessions allow easy revocation

**Reference**: See `def hash_token`, `def load_sessions`, `def save_sessions` in `src/api.py`

---

### Input Validation

**Backend validation pattern**:

```python
# Username validation
if len(username) < 3 or len(username) > 50:
    return error("Brugernavn skal vaere 3-50 tegn")

if not re.match(r'^[a-zA-Z0-9_]+$', username):
    return error("Brugernavn maa kun indeholde bogstaver, tal og underscore")

# Password validation
if len(password) < 8:
    return error("Adgangskode skal vaere mindst 8 tegn")

# Email validation (if provided)
if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
    return error("Ugyldig email adresse")

# Amount validation
try:
    amount = parse_danish_amount(amount_str)
    if amount <= 0:
        return error("Belob skal vaere storre end 0")
except ValueError:
    return error("Ugyldigt belob")
```

**Key points**:
- Always validate on backend (never trust frontend)
- Use specific error messages in Danish
- Validate format AND business rules

**Frontend validation**: Use `required` attribute and HTML5 types:

```html
<input type="email" required>
<input type="text" pattern="[a-zA-Z0-9_]+" required>
<input type="number" min="0" step="0.01" required>
```

---

## Database Patterns

### CRUD Operations

**All database operations follow this pattern**:

```python
def get_connection() -> sqlite3.Connection:
    """Get database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

**Read (SELECT)**:

```python
def get_something(user_id: int) -> Optional[SomeModel]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM table WHERE user_id = ? AND id = ?",
            (user_id, item_id)
        )
        row = cursor.fetchone()
        if row:
            return SomeModel(id=row['id'], field=row['field'])
        return None
```

**Create (INSERT)**:

```python
def add_something(user_id: int, field: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO table (user_id, field) VALUES (?, ?)",
            (user_id, field)
        )
        conn.commit()
        return cursor.lastrowid
```

**Update**:

```python
def update_something(item_id: int, user_id: int, field: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE table SET field = ? WHERE id = ? AND user_id = ?",
            (field, item_id, user_id)
        )
        conn.commit()
```

**Delete**:

```python
def delete_something(item_id: int, user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM table WHERE id = ? AND user_id = ?",
            (item_id, user_id)
        )
        conn.commit()
```

**Key points**:
- Always use `with get_connection()` context manager
- Always use parameterized queries (`?` placeholders) - NEVER string interpolation
- Always call `conn.commit()` for write operations
- Use `Row` factory for dict-like access
- Return typed dataclasses (not raw dicts)

**Reference**: See `src/database.py` for all CRUD implementations

---

### User Isolation

**CRITICAL: Always include user_id in WHERE clause for user data**

```python
# CORRECT - includes user_id
cursor.execute(
    "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
    (expense_id, user_id)
)

# WRONG - missing user_id (security vulnerability!)
cursor.execute(
    "SELECT * FROM expenses WHERE id = ?",
    (expense_id,)
)
```

**Pattern for all user data operations**:

```python
WHERE id = ? AND user_id = ?          # Read
UPDATE ... WHERE id = ? AND user_id = ?  # Update
DELETE ... WHERE id = ? AND user_id = ?  # Delete
```

Tables requiring user_id isolation: `income`, `expenses`, `categories`

---

## Testing Patterns

### Route Testing

**Test fixture** (`tests/conftest.py`):

```python
@pytest.fixture
def client():
    """Test client."""
    from src.api import app
    return TestClient(app)

@pytest.fixture
def authenticated_client(client):
    """Authenticated test client."""
    # Create test user and login
    # Returns client with session cookie
```

**Route test pattern**:

```python
def test_route_requires_auth(client):
    response = client.get("/budget/protected-route")
    assert response.status_code == 303
    assert response.headers["location"] == "/budget/login"

def test_route_success(authenticated_client):
    response = authenticated_client.get("/budget/route")
    assert response.status_code == 200
    assert b"Expected Content" in response.content

def test_route_post(authenticated_client):
    response = authenticated_client.post("/budget/route", data={
        "field1": "value1",
        "field2": "value2",
    })
    assert response.status_code == 303
```

**Reference**: See `tests/test_api.py` for all route tests

---

### Database Testing

**Test database setup** (`tests/conftest.py`):

```python
@pytest.fixture(autouse=True)
def reset_database():
    """Reset database before each test."""
    # Drop and recreate tables
```

**Database test pattern**:

```python
def test_create_user():
    user_id = db.create_user("testuser", "password123")
    assert user_id > 0

    user = db.get_user_by_username("testuser")
    assert user is not None
    assert user.username == "testuser"

def test_password_verification():
    db.create_user("testuser", "password123")
    assert db.authenticate_user("testuser", "password123") is not None
    assert db.authenticate_user("testuser", "wrongpassword") is None
```

**Reference**: See `tests/test_database.py` for all database tests

---

### E2E Testing

**Framework**: Playwright with pytest

**E2E test fixtures** (`e2e/conftest.py`):
- Provides `page` fixture (Playwright browser page)
- Provides `live_server` fixture (starts FastAPI server)

**E2E test pattern**:

```python
def test_login_flow(page, live_server):
    page.goto(f"{live_server}/budget/login")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r"/budget/$"))

def test_demo_mode(page, live_server):
    page.goto(f"{live_server}/budget/demo")
    expect(page.locator("text=Demo")).to_be_visible()
```

**Running tests**:

```bash
pytest tests/              # Unit tests
pytest e2e/                # E2E tests
pytest                     # All tests
pytest --collect-only      # List all test cases
```

**Reference**: See `e2e/test_auth.py`, `e2e/test_budget.py`, `e2e/test_demo.py`
