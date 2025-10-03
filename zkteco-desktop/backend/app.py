import os

from dotenv import load_dotenv

from zkteco import create_app

# Load environment variables from the .env file
load_dotenv()

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 57575))
    app.run(debug=True, port=port)
