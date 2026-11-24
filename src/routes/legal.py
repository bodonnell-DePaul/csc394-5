from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Legal"])


def render_page(title: str, content: str) -> HTMLResponse:
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>{title} | Healthwatch</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f4f7f9;
                color: #243447;
                margin: 0;
                line-height: 1.7;
            }}
            header {{
                background: #0f766e;
                color: white;
                padding: 20px 30px;
                font-size: 24px;
                font-weight: bold;
            }}
            main {{
                max-width: 800px;
                margin: 40px auto;
                padding: 35px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 15px #00000010;
            }}
            h1, h2 {{
                color: #0f766e;
            }}
            a {{
                color: #0f766e;
            }}
            footer {{
                text-align: center;
                padding: 25px;
                color: #64748b;
            }}
        </style>
    </head>
    <body>
        <header>Healthwatch</header>
        <main>
            <a href="/">&#8592; Back to Healthwatch</a>
            <h1>{title}</h1>
            <p>Last updated: November 24, 2026</p>
            {content}
        </main>
        <footer>
            Healthwatch | DePaul University Capstone Project
            <br>
            <a href="/privacy">Privacy Policy</a> |
            <a href="/terms">Terms of Service</a>
        </footer>
    </body>
    </html>
    """)


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return render_page("Privacy Policy", """
        <h2>1. About Healthwatch</h2>
        <p>
            Healthwatch is an educational software project developed
            as part of a DePaul University computer science capstone.
            The application demonstrates patient symptom tracking,
            medication management, and patient-provider interactions.
        </p>

        <h2>2. Information We Collect</h2>
        <p>
            Healthwatch may process account information, email
            addresses, patient identifiers, symptom reports,
            medication information, and authentication session data.
        </p>

        <h2>3. Google Authentication</h2>
        <p>
            Users who choose to sign in with Google authorize
            Healthwatch to receive basic identity information,
            including their Google account identifier, email address,
            and email verification status.
        </p>
        <p>
            This information is used to verify identity and determine
            whether the user is authorized to access a Healthwatch
            patient account. Healthwatch does not request access to
            Gmail messages, Google Drive files, or Google contacts.
            Healthwatch does not receive your Google password.
        </p>

        <h2>4. Use of Information</h2>
        <p>
            Information is processed to provide authentication,
            patient account functionality, symptom reporting,
            medication tracking, and authorized application features.
        </p>

        <h2>5. Data Storage and Security</h2>
        <p>
            Healthwatch uses a database to store application records
            and employs authentication and authorization controls
            to restrict access to application features.
            Session cookies are used to maintain authenticated sessions.
        </p>
        <p>
            The application is an educational prototype. Users should
            not submit real medical records, sensitive personal
            information, or confidential healthcare information.
        </p>

        <h2>6. Third-Party Services</h2>
        <p>
            Healthwatch uses Google for optional authentication
            and Render for application hosting. These services
            operate under their respective privacy policies.
        </p>
        <p>
            <a href="https://policies.google.com/privacy">
                Google Privacy Policy
            </a>
            <br>
            <a href="https://render.com/privacy">
                Render Privacy Policy
            </a>
        </p>

        <h2>7. Data Requests and Contact</h2>
        <p>
            Users may contact the Healthwatch development team
            to request information about their account or request
            deletion of their application data.
        </p>
        <p>
            Contact: joshualagunas65@gmail.com
        </p>

        <h2>8. Changes to This Policy</h2>
        <p>
            This privacy policy may be updated as the application
            and its functionality evolve.
        </p>
    """)


@router.get("/terms", response_class=HTMLResponse)
def terms_of_service():
    return render_page("Terms of Service", """
        <h2>1. Acceptance of Terms</h2>
        <p>
            By accessing Healthwatch, users agree to use the
            application in accordance with these terms.
        </p>

        <h2>2. Educational Purpose</h2>
        <p>
            Healthwatch is a computer science capstone project
            developed for educational and demonstration purposes.
            It is not a production medical service.
        </p>

        <h2>3. Medical Disclaimer</h2>
        <p>
            Healthwatch does not provide professional medical advice,
            diagnosis, treatment, or emergency medical services.
            Users should consult qualified healthcare professionals
            for medical concerns and treatment decisions.
        </p>

        <h2>4. Account Responsibilities</h2>
        <p>
            Users are responsible for protecting their account
            credentials and using only accounts and information
            they are authorized to access.
        </p>

        <h2>5. Acceptable Use</h2>
        <p>
            Users must not attempt to bypass authentication,
            access another user's information without permission,
            disrupt application services, or misuse application data.
            Users should use fictional or demonstration healthcare
            information rather than real medical records.
        </p>

        <h2>6. Service Availability</h2>
        <p>
            Healthwatch is provided as an educational prototype
            without guarantees of uninterrupted availability,
            accuracy, or fitness for clinical use.
        </p>

        <h2>7. Privacy</h2>
        <p>
            Information about data collection and authentication
            is available in our
            <a href="/privacy">Privacy Policy</a>.
        </p>

        <h2>8. Changes to These Terms</h2>
        <p>
            These terms may be updated as the project evolves.
        </p>

        <h2>9. Contact</h2>
        <p>
            Questions regarding Healthwatch may be directed
            to the development team.
        </p>
        <p>
            Contact: joshualagunas65@gmail.com
        </p>
    """)
