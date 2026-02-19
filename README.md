# LabTrack

Lab testing and COA management system built with Python, FastAPI, React, and SQLAlchemy.

## Features

- **COA Template Management**: Create, edit, and manage COA templates
- **Document Generation**: Generate COAs in multiple formats (DOCX, PDF)
- **AI-Powered Parsing**: Automatically extract information from COA documents
- **Folder Monitoring**: Watch folders for new COA files and process them automatically
- **Database Storage**: Store and retrieve COA data with full CRUD operations
- **Web Interface**: React-based frontend with modern UI
- **API Endpoints**: RESTful API for integration with other systems
- **Export Functionality**: Export COAs to Excel and other formats

## Project Structure

```
labtrack/
├── backend/              # FastAPI backend
│   ├── app/             # Application code
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── services/    # Business logic
│   │   ├── api/         # API endpoints
│   │   └── utils/       # Utility functions
│   └── tests/           # Pytest test suite
├── frontend/             # React + Vite frontend
├── templates/            # Document templates
├── .env.example          # Environment variables example
└── README.md            # This file
```

## Prerequisites

- Python 3.9 or higher
- pip or poetry for package management
- SQLite (default) or PostgreSQL/MySQL for production

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/labtrack.git
cd labtrack
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment variables:
```bash
cp .env.example .env
```

5. Edit `.env` with your configuration

6. Initialize the database:
```bash
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Usage

### Running the App

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8009

# Frontend
cd frontend && npm run dev
```

### Using the CLI

```bash
python -m src.cli --help
```

### Running Tests

```bash
pytest
```

### Code Formatting and Linting

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options.

Key configurations:
- `DATABASE_URL`: Database connection string
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`: For AI parsing features
- `WATCH_FOLDER_PATH`: Folder to monitor for new COAs
- `TEMPLATES_PATH`: Location of COA templates

## Development

### Setting up for Development

1. Install development dependencies:
```bash
pip install -r requirements.txt
```

2. Install pre-commit hooks (optional):
```bash
pre-commit install
```

### Adding New Features

1. Create feature branch from `main`
2. Add tests for new functionality
3. Implement the feature
4. Run tests and linting
5. Create pull request

### Database Migrations

When modifying database models:

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## API Documentation

The API endpoints are available at `/api/v1/` when running the application.

Main endpoints:
- `GET /api/v1/coas` - List all COAs
- `POST /api/v1/coas` - Create new COA
- `GET /api/v1/coas/{id}` - Get specific COA
- `PUT /api/v1/coas/{id}` - Update COA
- `DELETE /api/v1/coas/{id}` - Delete COA

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, email support@labtrack.com or create an issue in the GitHub repository.

## Acknowledgments

- Backend built with [FastAPI](https://fastapi.tiangolo.com/)
- Frontend built with [React](https://react.dev/) and [Vite](https://vitejs.dev/)
- Database ORM by [SQLAlchemy](https://www.sqlalchemy.org/)
- Document generation using [python-docx](https://python-docx.readthedocs.io/) and [ReportLab](https://www.reportlab.com/)