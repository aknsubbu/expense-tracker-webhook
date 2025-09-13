# Expense Tracker Webhook API

A FastAPI-based webhook service for tracking expenses and incomes, designed for integration with Apple Shortcuts and Google Sheets. This API allows you to log financial transactions directly into a Google Sheet, making it easy to automate and manage your expense tracking workflow.

---

## Features

- **Add Expense/Income**: Log transactions via a simple POST endpoint.
- **Google Sheets Integration**: Automatically appends entries to a specified Google Sheet.
- **Health Check**: Verify API and Google Sheets connectivity.
- **Cronjob Endpoint**: For scheduled maintenance or health checks.
- **CORS Support**: Ready for integration with web and mobile clients.
- **Structured Logging**: Logs all requests and errors to `expense_tracker.log`.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Google Sheets Setup](#google-sheets-setup)
- [API Endpoints](#api-endpoints)
- [Logging](#logging)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Requirements

- Python 3.10+
- Google Cloud Service Account with Sheets API access
- A Google Sheet for storing expenses

---

## Setup

1. **Clone the repository:**

   ```bash
   git clone <repo-url>
   cd expense-tracker-webhook
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Create and configure your `.env` file:**
   Copy `.env.example` to `.env` and fill in the required values (see [Environment Variables](#environment-variables)).

4. **Add your Google Service Account JSON:**
   Place your `service_account.json` in the project root (or update the path in `.env`).

---

## Environment Variables

Set the following variables in your `.env` file:

| Variable                      | Description                                                         |
| ----------------------------- | ------------------------------------------------------------------- |
| `GOOGLE_SHEETS_ID`            | The ID of your Google Sheet                                         |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to your service account JSON (default: `service_account.json`) |
| `SHEET_NAME`                  | Name of the sheet/tab (default: `Expense_Tracking`)                 |
| `PORT`                        | Port to run the API (default: `8000`)                               |
| `HOST`                        | Host to bind the server (default: `0.0.0.0`)                        |

---

## Google Sheets Setup

1. **Create a Google Sheet** and note its ID (from the URL).
2. **Create a Google Cloud Project** and enable the Google Sheets API.
3. **Create a Service Account** and download the JSON credentials.
4. **Share your Google Sheet** with the service account email (found in the JSON file) with Editor access.

---

## API Endpoints

### Root

- `GET /`
  - Returns API info and available endpoints.

### Health Check

- `GET /health`
  - Returns API status and Google Sheets connectivity.
  - **Response Example:**
    ```json
    {
      "status": "healthy",
      "timestamp": "2025-09-13T12:34:56.789Z",
      "version": "1.0.0",
      "google_sheets_connected": true
    }
    ```

### Add Expense/Income

- `POST /expense`
  - Adds a new expense or income entry to Google Sheets.
  - **Request Body:**
    ```json
    {
      "line_item": "Coffee",
      "amount": 3.5,
      "date_of_txn": "2025-09-13",
      "type": "Expense",
      "category": "Food"
    }
    ```
  - **Response Example:**
    ```json
    {
      "status": "success",
      "message": "Expense added successfully",
      "data": {
        "line_item": "Coffee",
        "amount": 3.5,
        "type": "Expense",
        "category": "Food",
        "date": "2025-09-13"
      },
      "timestamp": "2025-09-13T12:34:56.789Z"
    }
    ```

### Cronjob

- `POST /cronjob`
  - For scheduled maintenance tasks (e.g., verifying Google Sheets connectivity).
  - **Response Example:**
    ```json
    {
      "status": "success",
      "message": "Cron job completed successfully. Tasks: Google Sheets connectivity verified, Status logging completed",
      "timestamp": "2025-09-13T12:34:56.789Z"
    }
    ```

---

## Logging

- All requests and errors are logged to `expense_tracker.log`.
- Logs include timestamps, request/response info, and error details.

---

## Deployment

### Local Development

Run the API locally with auto-reload:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production

- Set `reload=False` in `main.py` or use a production server (e.g., Gunicorn with Uvicorn workers).
- Restrict CORS origins in production.

---

## Troubleshooting

- **Google Sheets not updating?**
  - Ensure the service account has Editor access to the sheet.
  - Check that `GOOGLE_SHEETS_ID` and `GOOGLE_SERVICE_ACCOUNT_FILE` are correct.
  - Review logs in `expense_tracker.log` for errors.
- **Validation errors?**
  - Ensure all required fields are present and correctly formatted.
- **API not starting?**
  - Check for missing environment variables or invalid credentials.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
