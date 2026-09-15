# Secure Question Paper System

## Project Description
A web-based application designed to prevent unauthorized access to examination question papers before the scheduled examination time. It provides role-based access for Admin, Setter, and Examiner users. The Setter uploads a question paper and sets the examination time; the Examiner can download it only after the permitted time.

The application is deployed on Microsoft Azure App Service and connected to GitHub using GitHub Actions.

## Technologies / Tools Used
- Python
- Flask
- HTML and CSS
- SQLite
- Fernet encryption
- Werkzeug password hashing
- Microsoft Azure App Service
- GitHub Actions (CI/CD)
- Git and GitHub
- Gunicorn
- Python 3.11
- Azure Blob Storage package

## Main Features
- Role-based login for Admin, Setter and Examiner
- Secure question paper upload
- Question paper encryption
- Examination-time restriction
- Download blocked before the permitted time
- Download allowed after the permitted time
- Audit logging
- Cloud deployment on Azure
- GitHub Actions CI/CD

## Project Structure
```text
secure-question-paper-system/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── .gitignore              # Git-excluded files
├── static/
│   └── style.css           # Web page styling
└── templates/
    ├── base.html           # Common layout
    ├── login.html          # Login page
    ├── dashboard.html      # Dashboard
    └── upload.html         # Upload page
```

## Installation and Running

### 1. Clone the repository
```bash
git clone https://github.com/pragadeesh1710/secure-question-paper-system.git
cd secure-question-paper-system
```

### 2. Create a virtual environment
```bash
python -m venv venv
```

### 3. Activate it

Windows:
```bash
venv\Scripts\activate
```

Linux/macOS:
```bash
source venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the application
```bash
python app.py
```

## Sample Input and Output

### Sample Input
Setter logs in, uploads a PDF question paper, and sets the examination time.
[(use id=setter,password=setter123)&&(id=examiner,password=examiner123)for login]

### Output Before Time
```text
Download restricted.
Question paper cannot be downloaded before the permitted examination time.
```

### Output After Time
```text
Download permitted.
Question paper can be downloaded successfully.
```

## Testing Performed
The deployed application was tested through the Azure public URL:
1. Setter login successful.
2. Question paper uploaded successfully.
3. Examination time configured.
4. Examiner attempted download before the permitted time.
5. Download was correctly blocked.
6. After the permitted time, download succeeded.

## Cloud Deployment
- Cloud Platform: Microsoft Azure
- Service: Azure App Service
- Deployment: GitHub Actions
- Runtime: Python 3.11
- OS: Linux
- Deployment Branch: `main`

### Live Application
https://secureqp20260914-app-g8bxa5akcxaagyac.indiasouthcentral-01.azurewebsites.net/login

### GitHub Repository
https://github.com/pragadeesh1710/secure-question-paper-system

## Security Note
Do not commit passwords, API keys, `.env` files, encryption keys, or other secrets to a public GitHub repository. Keep local secrets and sensitive runtime files excluded through `.gitignore`.

## Conclusion
The Secure Question Paper System demonstrates time-controlled and role-based question paper access. The source code is maintained on GitHub, and the application is deployed and tested successfully on Microsoft Azure App Service.
