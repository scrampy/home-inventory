# Home Inventory Web Application

This project is a web application for managing home inventory, designed for families. It uses a Flask backend and a React frontend.

## Project Structure

```
home-inventory/
├── backend/                # Flask backend
│   ├── app/                # Application code (models, routes, etc.)
│   ├── migrations/         # Database migrations (Flask-Migrate)
│   ├── requirements.txt    # Python dependencies
│   ├── config.py           # Configuration settings
│   └── run.py              # Entry point for Flask app
│
├── frontend/               # React frontend
│   ├── public/             # Static files
│   ├── src/                # React source code
│   ├── package.json        # Node dependencies and scripts
│   └── README.md
│
├── README.md               # Project overview and setup instructions
└── .gitignore
```

## Getting Started

### Backend (Flask)
1. Navigate to the `backend` directory
2. Create a virtual environment and activate it
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `python run.py`

### Frontend (React)
1. Navigate to the `frontend` directory
2. Install dependencies: `npm install`
3. Start the app: `npm start`

## What a Clean Rewrite Should Look Like

- **App Structure:**
  - One main App component with a simple screen state (e.g., `screen`).
  - Dedicated components for ItemList, ItemForm, StoreList, StoreForm, etc.
- **Navigation:**
  - Minimal, explicit navigation logic (e.g., `useState('screen')`).
- **Form Handling:**
  - Each form manages its own state.
  - On error, error messages are displayed inline, input is preserved, and navigation does not change.
- **API Calls:**
  - Simple fetch/axios calls with clear error handling.
- **No Over-Engineering:**
  - No unnecessary keys, localStorage hacks, or defensive double state.
- **Testing:**
  - Easy to test and reason about each component.

## Recommendations

- **Start a new, clean repo or directory.**
  - Scaffold the app with Create React App or Vite (for frontend), Flask/FastAPI (for backend if using Python).
  - Implement only the core screens and flows.
  - Keep state and navigation logic as simple as possible.
  - Add error handling as a first-class concern in each form.

**Estimated time for a working CRUD app:**
- **Frontend:** 1–2 days for all screens and error handling.
- **Backend:** 1 day for REST endpoints and DB models.

A clean rewrite will be faster, simpler, and more maintainable than continuing to patch the current codebase.

---

This project is in the early stages. See `HomeInventorySpec.md` for the specification.
