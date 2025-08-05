from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scraper import scrape_attendance
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Email config
FROM_EMAIL = os.getenv("FROM_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))

# FastAPI setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://attendify-dashboard-prohub.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class LoginRequest(BaseModel):
    reg_no: str
    password: str

# Email sender function
def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    # Attach HTML content
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(FROM_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            print("✅ Email sent successfully")
    except Exception as e:
        print("❌ Email failed:", e)

@app.post("/attendance")
def get_attendance(data: LoginRequest):
    try:
        result = scrape_attendance(data.reg_no, data.password)

        # Validation
        if "detail" in result and result["detail"].startswith("400:"):
            raise HTTPException(status_code=400, detail="Invalid username or password.")
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Compose and send HTML email
        name = result.get("name", "Student")
        total = result.get("total_classes", 0)
        present = result.get("present", 0)
        absent = result.get("absent", 0)
        percent = result.get("percentage", 0)
        now = datetime.now()
        formatted = now.strftime("%d-%b-%Y %I:%M %p")
        print(formatted)

        body = f"""
        <html>
        <head>
          <style>
            table {{
              border-collapse: collapse;
              width: 100%;
              max-width: 400px;
              font-family: Arial, sans-serif;
            }}
            th, td {{
              border: 1px solid #ddd;
              padding: 8px 12px;
              text-align: left;
            }}
            th {{
              background-color: #4CAF50;
              color: white;
              font-weight: bold;
            }}
            h2 {{
              font-family: Arial, sans-serif;
              color: #333;
            }}
            p {{
              font-family: Arial, sans-serif;
              color: #555;
            }}
          </style>
        </head>
        <body>
          <p>Hello MITSian,</p>
          <p><b>Name:</b> {name}<br/>
          <b>Roll No:</b> {data.reg_no}<br/>
          <b>Date & Time:</b> {formatted}</p>

          <h2>📘 Here’s your latest Attendance Report:</h2>
          <table>
            <tr>
              <th>Category</th>
              <th>Details</th>
            </tr>
            <tr>
              <td><b>Total Classes Conducted</b></td>
              <td>{total}</td>
            </tr>
            <tr>
              <td><b>Classes Attended</b></td>
              <td>{present}</td>
            </tr>
            <tr>
              <td><b>Classes Missed</b></td>
              <td>{absent}</td>
            </tr>
            <tr>
              <td><b>Attendance Percentage</b></td>
              <td>{percent}%</td>
            </tr>
          </table>

          <p><b>Feedback:</b> {("Excellent work! Your consistency is commendable. 👏" if percent >= 80 else 
           "Good going! Aim a little higher for excellence. 💪" if percent >= 75 else 
           "Your attendance is below expected levels. Please improve to stay eligible. ⚠️")}</p>

          <p>Note: This attendance is calculated using the base formula:<br/>
          (Total Attended / Total Conducted) × 100</p>

          <p>– MITS Attendance System</p>
        </body>
        </html>
        """

        recipient = f"{data.reg_no}@mits.ac.in"
        send_email(recipient, "Your Attendance Report", body)

        # Return result to frontend
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the MITS Attendance API. Use the /attendance endpoint to get your attendance report."}
