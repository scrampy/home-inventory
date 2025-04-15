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

---

This project is in the early stages. See `HomeInventorySpec.md` for the specification.
