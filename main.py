from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
import logging
from datetime import datetime, date
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import uvicorn
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('expense_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Expense Tracker API",
    description="API for tracking expenses via Apple Shortcuts and managing Google Sheets integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    SHEET_NAME = os.getenv("SHEET_NAME", "Expense_Tracking")
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")

config = Config()

# Pydantic models
class ExpenseEntry(BaseModel):
    line_item: str
    amount: float
    date_of_txn: str  # Expected format: YYYY-MM-DD
    type: str  # "Expense" or "Income"
    category: str
    
    @validator('type')
    def validate_type(cls, v):
        if v.lower() not in ['expense', 'income']:
            raise ValueError('Type must be either "Expense" or "Income"')
        return v.title()
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return round(v, 2)
    
    @validator('date_of_txn')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
    
    @validator('line_item', 'category')
    def validate_non_empty_strings(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    google_sheets_connected: bool

class CronJobResponse(BaseModel):
    status: str
    message: str
    timestamp: str

# Google Sheets Service
class GoogleSheetsService:
    def __init__(self):
        self.service = None
        self.sheets_id = config.GOOGLE_SHEETS_ID
        self.sheet_name = config.SHEET_NAME
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets API service"""
        try:
            # Check if service account file exists
            if not Path(config.GOOGLE_SERVICE_ACCOUNT_FILE).exists():
                logger.error(f"Service account file not found: {config.GOOGLE_SERVICE_ACCOUNT_FILE}")
                return
            
            # Define the scope
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Load credentials
            credentials = Credentials.from_service_account_file(
                config.GOOGLE_SERVICE_ACCOUNT_FILE, 
                scopes=SCOPES
            )
            
            # Build the service
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {str(e)}")
            self.service = None
    
    def is_connected(self) -> bool:
        """Check if Google Sheets service is connected"""
        return self.service is not None
    
    def ensure_sheet_exists(self):
        """Ensure the sheet exists and has proper headers"""
        if not self.service:
            raise Exception("Google Sheets service not initialized")
        
        try:
            # Try to get the sheet
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.sheets_id
            ).execute()
            
            # Check if our sheet exists
            sheet_exists = False
            for sheet in sheet_metadata.get('sheets', []):
                if sheet.get('properties', {}).get('title') == self.sheet_name:
                    sheet_exists = True
                    break
            
            # Create sheet if it doesn't exist
            if not sheet_exists:
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': self.sheet_name
                        }
                    }
                }]
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheets_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info(f"Created new sheet: {self.sheet_name}")
            
            # Check if headers exist, if not add them
            range_name = f'{self.sheet_name}!A1:F1'
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheets_id, 
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values[0]) < 6:
                # Add headers
                headers = [['Timestamp', 'Line Item', 'Amount', 'Date of Transaction', 'Type', 'Category']]
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheets_id,
                    range=f'{self.sheet_name}!A1:F1',
                    valueInputOption='RAW',
                    body={'values': headers}
                ).execute()
                logger.info("Added headers to sheet")
                
        except HttpError as e:
            logger.error(f"Google Sheets API error: {str(e)}")
            raise Exception(f"Failed to access Google Sheets: {str(e)}")
    
    def add_expense(self, expense: ExpenseEntry) -> bool:
        """Add expense entry to Google Sheets"""
        if not self.service:
            raise Exception("Google Sheets service not initialized")
        
        try:
            # Ensure sheet exists and has headers
            self.ensure_sheet_exists()
            
            # Prepare the row data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [[
                timestamp,
                expense.line_item,
                expense.amount,
                expense.date_of_txn,
                expense.type,
                expense.category
            ]]
            
            # Append the row
            range_name = f'{self.sheet_name}!A:F'
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheets_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': row_data}
            ).execute()
            
            logger.info(f"Added expense entry: {expense.line_item} - {expense.amount}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to add expense to Google Sheets: {str(e)}")
            raise Exception(f"Failed to add expense: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error adding expense: {str(e)}")
            raise Exception(f"Failed to add expense: {str(e)}")

# Initialize Google Sheets service
sheets_service = GoogleSheetsService()

# Middleware for logging requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Log the request
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log the response
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response

# API Endpoints

@app.get("/", summary="Root endpoint")
async def root():
    """Root endpoint with basic API information"""
    return {
        "message": "Expense Tracker API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "add_expense": "/expense (POST)",
            "cronjob": "/cronjob (POST)"
        }
    }

@app.get("/health", response_model=HealthResponse, summary="Health check endpoint")
async def health_check():
    """Health check endpoint to verify API and Google Sheets connectivity"""
    try:
        google_connected = sheets_service.is_connected()
        
        # Try to access the spreadsheet if connected
        if google_connected:
            try:
                sheets_service.ensure_sheet_exists()
            except Exception as e:
                logger.warning(f"Google Sheets accessible but error ensuring sheet: {str(e)}")
                google_connected = False
        
        return HealthResponse(
            status="healthy" if google_connected else "degraded",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            google_sheets_connected=google_connected
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/expense", summary="Add expense entry")
async def add_expense(expense: ExpenseEntry, background_tasks: BackgroundTasks):
    """
    Add an expense entry to Google Sheets.
    
    This endpoint accepts expense data from Apple Shortcuts and saves it to Google Sheets.
    """
    try:
        logger.info(f"Received expense entry: {expense.line_item} - ${expense.amount}")
        
        # Validate Google Sheets connection
        if not sheets_service.is_connected():
            raise HTTPException(
                status_code=503, 
                detail="Google Sheets service not available"
            )
        
        # Add expense to Google Sheets
        success = sheets_service.add_expense(expense)
        
        if success:
            return {
                "status": "success",
                "message": "Expense added successfully",
                "data": {
                    "line_item": expense.line_item,
                    "amount": expense.amount,
                    "type": expense.type,
                    "category": expense.category,
                    "date": expense.date_of_txn
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add expense")
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in add_expense: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/cronjob", response_model=CronJobResponse, summary="Cron job endpoint")
async def cronjob_endpoint(background_tasks: BackgroundTasks):
    """
    Endpoint for cron jobs to perform maintenance tasks.
    
    This can be called by external cron services to perform periodic maintenance,
    cleanup, or health checks.
    """
    try:
        logger.info("Cron job endpoint called")
        
        # Perform maintenance tasks
        tasks_performed = []
        
        # Task 1: Check Google Sheets connectivity
        if sheets_service.is_connected():
            try:
                sheets_service.ensure_sheet_exists()
                tasks_performed.append("Google Sheets connectivity verified")
            except Exception as e:
                tasks_performed.append(f"Google Sheets check failed: {str(e)}")
        else:
            tasks_performed.append("Google Sheets service not connected")
        
        # Task 2: Log current status
        tasks_performed.append("Status logging completed")
        
        # Task 3: You can add more maintenance tasks here
        # Example: Clean up old logs, validate data integrity, etc.
        
        logger.info(f"Cron job completed. Tasks: {', '.join(tasks_performed)}")
        
        return CronJobResponse(
            status="success",
            message=f"Cron job completed successfully. Tasks: {', '.join(tasks_performed)}",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Cron job failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cron job failed: {str(e)}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return {
        "status": "error",
        "message": "Endpoint not found",
        "path": str(request.url.path),
        "timestamp": datetime.now().isoformat()
    }

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    logger.error(f"Internal server error on {request.url.path}: {str(exc)}")
    return {
        "status": "error",
        "message": "Internal server error",
        "timestamp": datetime.now().isoformat()
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting up Expense Tracker API")
    
    # Verify configuration
    required_env_vars = ["GOOGLE_SHEETS_ID"]
    missing_vars = [var for var in required_env_vars if not getattr(config, var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
    
    # Initialize Google Sheets service
    if sheets_service.is_connected():
        logger.info("Google Sheets service connected successfully")
    else:
        logger.warning("Google Sheets service not connected - check configuration")
    
    logger.info("Startup completed")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Expense Tracker API")

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "main:app",  # Assumes this file is named main.py
        host=config.HOST,
        port=config.PORT,
        reload=True,  # Remove in production
        log_level="info"
    )